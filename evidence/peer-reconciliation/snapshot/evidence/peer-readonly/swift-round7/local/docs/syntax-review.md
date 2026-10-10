# Syntax review

The design target is explicit types and predictable native behavior with little
ceremony: TypeScript-like annotations, Swift-like readable value operations,
and C++-class code generation. A smaller vocabulary is preferable to adding
synonyms for existing declarations.

This pass removes two formatting traps. Parenthesized and bracketed expressions
can span lines without a trailing comma, and `else` can follow a newline. The
bootstrap and self-hosted lexers agree. Newlines still separate statements outside
those delimiters; record bodies retain their field separators. Regression tests
exercise both direct and module compilation, including comments between branches.

Constant declarations now validate their values even if nobody uses them. Local
bindings and function parameters consistently shadow constants. Invalid native
declarations report source errors before malformed LLVM or conflicting ABI
declarations can reach Clang. These are part of the syntax experience: a program
should have the same meaning across compilation paths and diagnostics should name
the language construct that is wrong.

Keep the following existing choices:

- One equality operator with no coercion; explicit Integer/Float conversion.
- Type inference where the value determines the type, including contextual empty Lists.
- Explicit module namespaces and `public` at the interface boundary.
- Automatic ownership with no required lifetime, allocator, or borrow syntax.
- Checked ordinary arithmetic, with explicitly named wrapping operations.

The next substantive simplifications need representations and semantic work,
not more surface spelling. Conditional expressions would remove temporary locals
but require branch type joining and ownership transfer tests. Local immutable
bindings need a deliberate decision about `let`, which currently means a mutable
binding. Generic functions and richer inferred return types need stable module
interfaces and diagnostics before syntax is promised. Source formatting and an
editor service should share the compiler's token/span model instead of a second
approximate parser.

Acceptance for a future syntax change: fewer concepts or less ceremony in actual
examples; no ambiguity introduced by line wrapping; identical meaning through
direct, module, and optimized builds; exact rejecting diagnostics; and a clear
migration when existing valid programs change meaning. The user has authorized
breaking changes for demonstrated ergonomic gains, but this pass's newline
improvements also preserve existing programs.
