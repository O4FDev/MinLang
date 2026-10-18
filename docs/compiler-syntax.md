# Compiler syntax tree

Each `CompilerContext` owns a `SyntaxTree`. The tree describes normalized
Minyar syntax, after the existing callable and Result transformations. The
checker records statement and expression nodes while emitting LLVM; it does
not run a second expression parser. Declaration nodes reuse the module scan's
token ranges when those ranges are available.

Function emission consumes declaration nodes, typed parameter children and
stored body starts. It does not parse signatures or skip other declarations
again. Its body parser still consumes tokens. Migration to tree consumers is
staged, so declaration discovery and some ownership lookahead helpers still
scan tokens.

## Representation

`compiler/stages/syntax.min` defines the tree, its builder and source spans.
`CompilerContext` is defined there too: stage0 requires a record type to be
declared before another record uses it as a field.

Nodes have stable Integer IDs into `tree.nodes`, a `List<SyntaxNode>`. Each
node stores its kind, resolved type, half-open token range, parent, first/last
child, previous/next sibling, symbol, body start and operator token. Links are
Integer IDs, keeping the managed object graph flat and teardown iterative.

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
- 100–111: block, conditional, loop, binding, return, jump, match, native body,
  expression statement and assignment.
- 200–221: names, literals, collections, groups, closures, calls, record
  literals, members, indexes, assignment targets and operators.

To add a kind, extend that catalogue and its structural probe. Call
`beginSyntaxNode` before consuming its syntax, then `endSyntaxNode` with the
resolved type and cursor after the node. These helpers check balanced
parentage. Use `wrapSyntaxOperand` for postfix or binary operations so the
existing receiver or left operand remains a typed child.

## Source spans and diagnostics

Every node retains its token range and the shared `SourceMap`. Locations stay
numeric during successful compilation; formatting is deferred until needed.

```minyar
let span = syntaxSpan(context.syntax, node)
let location = describeSpan(span) // file:line:column
```

`SourceSpan` contains `file`, `line`, `column`, `firstToken` and `afterToken`.
Lines and columns retain the full Integer width. Columns count Unicode scalar
values, matching the lexer. Cached legacy origins are decoded on demand, and
per-token module paths take precedence over the entry file.

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
range but no node. Existing diagnostic text keeps its established formatter;
converting every old failure to this API is a separate migration.

## Checks

`make check-syntax-tree` verifies resolved types, precedence, sibling and
parent links, contained ranges, reachability, Unicode and cached locations,
the error API and 50,000 nested builder nodes. It also checks contextual names,
quoted keywords and the operator on `try` expressions. The observatory gallery and
expression fixtures run at O0/O2 with ownership assertions. The ordinary
conformance and example corpora separately check emitted LLVM bytes.
