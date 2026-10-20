# Compiler syntax tree

Each `CompilerContext` owns a `SyntaxTree`. The tree describes normalized
Minyar syntax, after the existing callable and Result transformations. The
checker records statement and expression nodes while emitting LLVM; it does
not run a second expression parser. Declaration nodes reuse the module scan's
token ranges when those ranges are available.

Function emission consumes declaration nodes, typed parameter children and
stored body starts. It does not parse signatures or skip other declarations
again. Initial record and constant name collection also walks those nodes in
ordinary and cached-interface compilation; the duplicate discovery scanners
have been removed. Header type checking and body emission still consume
tokens, as do some ownership lookahead helpers.

Index ownership lookahead uses `callFreeIndexes`, a token-addressed Boolean
column prepared in one linear pass. `syntaxIndexHasNoCalls` answers in constant
time, including for nested brackets; the old `indexWithoutCalls` scanner has
been removed. These are lexical facts needed before an index expression is
checked, rather than semantic call-effect analysis. A closing bracket followed
by a callback call counts as a call, preserving the existing ownership rule.

## Representation

`compiler/stages/syntax.min` defines the tree, its builder and source spans.
`CompilerContext` is defined there too: stage0 requires a record type to be
declared before another record uses it as a field.

Nodes have stable Integer IDs into `tree.nodes`, a `List<SyntaxNode>`. Each
node stores its kind, resolved type, half-open token range, parent, first/last
child, previous/next sibling, symbol, body start, operator token and documentation.
Links are Integer IDs, keeping the managed object graph flat and teardown iterative.

Record lists are supported by the bootstrap compiler. A construction and
sibling-traversal comparison over 100,000 nodes at O2 used 132.3 million retired
instructions for records versus 349.5 million for parallel Integer columns.
Peak resident memory was 15.4 MiB versus 18.3 MiB. The tree therefore uses
records; the initial column prototype was more expensive on this runtime.

Node IDs are not a traversal order. Wrapping an existing operand creates a
new parent with a later ID. Traverse the child and sibling links instead.
`wrapSyntaxOperand` replaces the final child in constant time, preserving
the parser's precedence and associativity. Construction and traversal need
no recursive walk of the tree.

A safe `parallel for` reuses loop kind 103. Its body is checked using typed
name, index and assignment-target children before outlining worker LLVM.
For a reduction, the loop's operator token is `reduce` and its symbol is the
existing mutable accumulator binding. No extra syntax kind or type tag is used.

`nodes[node].type` uses the compiler's existing type codes. Zero means that a node
is still being constructed; checked trees have resolved types. Module,
statement and block nodes use `Nothing`. A function declaration stores its
return type; parameter children carry the parameter types. Record field and
parameter nodes span the binding name and refer to their type-table offset.
Folded negative numeric literals span both the minus and the digits.
Parameter names come from the shared declaration table through that offset;
later consumers need not read their header tokens.

`declarations` lists declarations in source order. `symbolNodes[symbol]`
finds their node without a scan. Internal callback environment symbols map
to their closure expression; synthetic symbols without a source declaration
have no node. Literal module initializers get typed literal children, and
runtime initializers get the expressions recorded by their checker.

## Node kinds

`syntaxKindName` is the central catalogue. The ranges are registered in the
overnight charter and are separate from lexer and type codes:

- 0: module.
- 1–6: function, record, constant, global, field and parameter.
- 7–9: choice, type alias and test in raw documentation trees. Typed compilation
  continues to describe normalized declarations with the existing kinds.
- 100–111: block, conditional, loop, binding, return, jump, match, native body,
  expression statement and assignment.
- 200–221: names, literals, collections, groups, closures, calls, record
  literals, members, indexes, assignment targets and operators.

To add a kind, extend that catalogue and its structural probe. Call
`beginSyntaxNode` before consuming its syntax, then `endSyntaxNode` with the
resolved type and cursor after the node. These helpers check balanced
parentage. Use `wrapSyntaxOperand` for postfix or binary operations so the
existing receiver or left operand remains a typed child.

## Documentation metadata

The lexer captures actual leading `///` comments, so quoted or interpolated
text cannot become documentation. Consecutive comment lines attach to the
immediately following declaration or binding; a blank source line detaches
them. `SourceMap.documentation` is a sparse-prefix token column, preserved by
`copyModuleToken`. `appendSyntaxNode` copies its text to the node's
`documentation` field. The module root does not inherit a declaration's comment.

`--doc-json` builds a raw source tree instead of normalizing generics, choices
and methods. Its version 1 JSON contains public declarations with `name`, `kind`,
`signature`, `documentation`, `span` and `members`, plus a separate `tests`
array with names and spans. Signatures retain the original source spelling;
members include public record fields and choice cases. Private fields are
excluded. Source offsets are indexed once, and field boundaries follow the
type grammar rather than relying on newline tokens after generic brackets.

This mode reloads original source and bypasses incremental interface caches.
Cached interfaces remain a compilation representation, not a documentation
archive. The metadata mode emits no executable program and does not replace
type checking. Ordinary compilation emits identical LLVM with `///` and `//`.

## Source spans and diagnostics

Every node retains its token range and the shared `SourceMap`. Locations stay
numeric during successful compilation; formatting is deferred until needed.

```minyar
let span = syntaxSpan(context.syntax, node)
let location = describeSpan(span) // file:line:column
```

`SourceSpan` contains `file`, `line`, `column`, `firstToken` and `afterToken`.
Lines and columns retain the full Integer width. Columns count Unicode scalar
values, matching the lexer. Cached legacy origins are decoded on demand and
retain filename punctuation. Per-token module paths take precedence over the
entry file.

`SourceMap.inputPath` supplies the file for an ordinary entry module. It is
separate from the existing debug-origin path representation, so recording the
tree preserves generated LLVM bytes. Token transformations carry it through
`copyModuleToken`. An in-memory source without a filename uses `<source>`.

New checks can report a node or token directly:

```minyar
failAtSyntax(context.syntax, node, "expected a value")
failAtToken(context.tokenLines, position, "expected a value")
```

`sourceSpan(map, file, first, after)` also serves diagnostics that have a token
range but no node. `compiler/stages/diagnostics.min` renders these spans with
the original source line and a token underline. `failDiagnostic` also accepts
an underline label and a help note. Cached declaration origins use the same
span decoder. Lexical failures retain the current module's filename.

Diagnostic source rereads and formatting happen only on failure. An unavailable source
file keeps its location and message. Tabs display as four spaces, CRLF source
lines lose their carriage return, and terminal control characters are escaped.
Older checks are being moved to these helpers without changing their meaning.

## JSON diagnostics

`--error-format json` writes one JSON object per error to standard error,
with no diagnostic output on success. Exit status remains 1 for rejected input.
The standalone launcher and incremental module driver forward this option.

Schema version 1 always includes `version` (1), `severity` ("error"),
`code` (such as "E0401"), `message`, `file`, `line`, `column`, `endLine`, `endColumn`, `sourceLine`,
`label`, and `help` (an array of strings). Positions are 1-based Unicode scalar
columns, with an exclusive end. An empty range marks end of input. `sourceLine`
is the original line without its line ending; `label` may be empty.
JSON preserves source characters and escapes control characters. Tools using
UTF-16 positions can convert columns from `sourceLine`.

`code` is an additive version-1 field. Consumers should accept unknown fields.
Every compiler diagnostic has a repair note; a specific spelling suggestion
takes precedence over the advice for its family. Human output ends with
`= explain: minyar explain CODE`. The same compiler embeds the catalogue used
by `minyar explain CODE` and `minyar explain --list`, so installed explanations
match the toolchain without reading a project or downloading documentation.
The catalogue maps legacy message families to stable codes; E0001 covers checks
that do not yet have a dedicated family. All recorded error goldens require a
specific code. New message families should receive a code and a tested example.

Explicit compiler rejections share the central formatter. Legacy messages
keep their original decoded locations. Within a checked body, an older caller
can use the active job's token; callers before body checking still fall back
to the input file's first position while their spans are migrated.

Recovery resumes at a complete function declaration or top-level statement,
up to 20 errors. A failed function contributes one primary error. References
to a failed top-level binding are suppressed until a valid shadowing binding
is available. Lexical, header and structural failures stop when no safe
boundary is known. No partially generated LLVM is written.

The private `diagnostics` native body supplies a live C boundary around a
Minyar compilation job. Explicit diagnostics release heap and live stack
ownership frames before jumping, then restore call depth. Runtime faults are
not caught. Stage0 validates the callback signature before emitting LLVM.

## Checks

`make check-syntax-tree` verifies resolved types, precedence, sibling and
parent links, contained ranges, reachability, Unicode and cached locations,
the error API and 50,000 nested builder nodes. It also checks contextual names
(including ordinary locals named `Map` and `Set`), quoted keywords and the operator
on `try` expressions. The observatory gallery and
expression fixtures run at O0/O2 with ownership assertions. The ordinary
conformance and example corpora separately check emitted LLVM bytes.

Compiler input reading also uses the diagnostic boundary: missing files,
directories and invalid UTF-8 become structured errors instead of raw runtime
stops. The first invalid byte is displayed as a replacement character, with
a best-effort source prefix. Display-cell ranges follow Unicode 14.0 assigned
wide/full-width and combining categories, plus common emoji sequences. JSON
positions remain scalar offsets and preserve the original valid source line.

## Runtime trace metadata

`runtime-traces.min` records readable names and original token locations while
functions, closures and runtime global initializers are emitted. Each cached module
owns a table of relative string offsets; the final registry is rebuilt from
its current module graph, even on a cache hit. No function address is retained
by a row, so unused functions still disappear during LTO. LLVM `uwtable`
attributes preserve existing unwind descriptions without injected trace calls.

The private runtime ABI uses 32-byte rows (four i32 fields and two i64 source
coordinates) and an eight-byte module registry row. Offsets are signed i32
relative to their table and resolved by the static linker. They add no PIE
pointer fixups. The cold Mach-O reader resolves symbols from loaded __LINKEDIT
and walks ARM64 compact unwind/DWARF CFI. Linux reads ELF symbols only after a
failure and uses the platform unwinder. If symbols or unwind information are
unavailable, the registry supplies an entry location. No C runtime failure is
caught or converted to recoverable control flow by this reporter.

The JSON contract covers explicit compiler diagnostics and source-read errors.
Host failures writing LLVM or cache files still use runtime reports. Hosted Linux currently loads libgcc_s for unwinding; this is a fixed
startup cost, so a strict zero-instruction claim does not apply there.
