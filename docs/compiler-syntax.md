# Compiler syntax tree

Each `CompilerContext` owns a `SyntaxTree`. The tree describes normalized
Minyar syntax, after the existing callable and Result transformations. The
checker records statement and expression nodes while emitting LLVM; it does
not run a second expression parser. Declaration nodes reuse the module scan's
token ranges when those ranges are available.

User-defined capabilities are checked during generic normalization. Their
signatures use the same type shapes as generic declarations. Conformance checking
resolves aliases before comparing methods; defaults become ordinary concrete
method declarations with an explicit receiver. Copied tokens preserve their
capability module's source spans. Capability declarations and conformance
statements emit no runtime representation. Raw documentation trees use kind 10
for capabilities and ordinary function nodes for their method signatures. The
compiler embeds the ordinary built-in capability declarations at bootstrap time.
Explicit built-in conformances add empty compiler-only record symbols keyed by
the receiver and capability; they allocate no values and emit no runtime tables.
Derived operation wrappers call the checked concrete methods. Call-effect and
cooperative-recovery hooks run at each actual operator or collection use, even
when an operation wrapper was already emitted for another function.

Enabled header contracts become ordinary wrapper and body functions before
module qualification. Their synthetic checks retain each clause's original
source span. Release removes the clauses before feature discovery; test mode
keeps them. Compile-time Integer expressions fold to literal tokens before
typed declaration discovery, preserving their source origins. Raw incremental
state signatures include the contract profile, as does the native cache driver,
so changing profiles cannot reuse a function compiled with different checks.

Wrappers always carry an internal outcome token. Typed emission omits its
storage, result alias and value return when the resolved return type is Nothing,
including aliases and generic substitutions. User Nothing bindings still reject.
Contract diagnostics use static metadata and exact compiler-generated cold
failure functions, so scalar parallel predicates need no managed values.

Immutable module Integer tables retain kind 3 symbols and canonical folded
bracket initializers. Integer return-type metadata is an internal dispatch marker;
the table name never becomes a first-class Integer value. `parseAtom` resolves
local shadows before checking for a bracket initializer, then consumes indexing
or `.length`. Index/member nodes retain a name receiver and source span. Native
array lengths can include a constant table lookup. Generic inference temporarily
uses a `List<Integer>` shape for member/index result inference; the emitting
checker still rejects table aliases and mutation. No new type tag is allocated.

The existing constant-declaration incremental fallback remains in force. Table
sources publish empty state and compile through the complete qualified module
graph, in debug and release profiles.

Function emission consumes declaration nodes, typed parameter children and
stored body starts. It does not parse signatures or skip other declarations
again. Initial record and constant name collection also walks those nodes in
ordinary and cached-interface compilation; the duplicate discovery scanners
have been removed. Header type checking and body emission still consume
tokens, as do some ownership lookahead helpers.

Reference returns inspect the completed typed expression. A direct local name
must be a one-token leaf, optionally wrapped in grouping nodes. It is a last use
on that return path and can transfer its local owner. A complete return of a Text join or List `appended`
can also consume a named local left operand or receiver, after all arguments
have run. Other member, index and call receivers keep their existing rules.
These proofs need no future-token scan and do not assume heap uniqueness.
Direct local reassignment uses the same completed-root proof when the receiver
is the binding being replaced. Same-source RHS reads finish before the move;
assignments to another binding and implicit compound-assignment roots do not
use this proof. The older lexical chain fast path remains available.

One `TerminalReuseSite` per compiler context remembers the most recently emitted
ordinary join or append: its typed node, receiver SSA value and two stable output
fragment indexes. The final eligible root must match that exact node, ignoring
groups. Inner expressions and stale sites cannot match. Filling a reserved
fragment inserts the local-owner move immediately before the consumer; changing
its callee fragment selects the existing uniqueness-checked runtime operation.
Cycle fixups retain their original fragment indexes. Metadata uses constant
space; proof traversal visits only the root's and receiver's grouping nodes.

Primitive heap-record reconstruction uses a separate `RecordReuseSite`. The
completed assignment root must be a constructor of the target's nominal type,
with at most sixteen Integer, Float, Boolean or Character fields. The site
records stable allocation/owner and setter fragment ranges. All initializers
evaluate before a late local-owner move and uniqueness-checked reuse helper;
the allocation owner and field stores move after that helper. This preserves
swaps, calls that mutate the old record and early Result propagation. Nested
constructors, C layouts, choices, callback-enabled jobs and recovery keep their
previous lowering. The sixteen-field limit bounds deferred metadata and copying.

Scalar-record escape analysis remains a budgeted lexical proof. Readonly
candidates keep captured SSA fields; candidates with direct field writes use
entry-block i64 slots and fresh loads at each field read. An explicit metadata
tag distinguishes these representations. The existing whole-object escape
guards, constructor order and proof-attempt budget also apply to writable fields.

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

User-record `for` loops also use kind 103. Their source remains a typed child;
the checker resolves the concrete `iterator`, `advance` and `current` symbols
and records their call dependencies before emitting ordinary loop blocks.
There is no new syntax kind, type tag or runtime iteration ABI.

Match patterns use a separate flat `MatchPattern` tree in `compiler/patterns.min`.
Constructor tests branch before loading payloads; bindings acquire ownership only
after the whole pattern succeeds. A false guard clears those binding roots before
trying the next arm. Coverage specializes a matrix of unguarded patterns by
constructor, preserving relationships between payloads and rebuilding a missing
example from the uncovered row. This analysis emits no runtime coverage code.
Patterns are limited to 128 nesting levels; coverage has a bounded work budget
and requests an `else` arm if that budget is exhausted.

Contextual `if`/`while` checks and `let` destructuring use the same pattern tree
and coverage checker through `compiler/pattern-bindings.min`. Ordinary records
are single-constructor products with positional fields and normal private-field
checks. A conditional owns its input until all tests finish, then installs its
binding roots. The enclosing body owns those roots, including on loop jumps.
`let` resolves its right side before its pattern names and rejects a missing
coverage witness. Existing statement syntax kinds remain unchanged.

Integer ranges use pattern kind4 and canonical literal endpoints. Runtime tests
use signed comparisons without subtraction. Coverage builds disjoint cells at
all literal/range boundaries, guarding successor arithmetic at the maximum
Integer. It specializes complete rows for each cell, preserving correlations
with later fields. Text remains an open literal domain with exact-content
comparison and a wildcard/default requirement.

`nodes[node].type` uses the compiler's existing type codes. Zero means that a node
is still being constructed; checked trees have resolved types. Module,
statement and block nodes use `Nothing`. A function declaration stores its
return type; parameter children carry the parameter types. Record field and
parameter nodes span the binding name and refer to their type-table offset.
Folded negative numeric literals span both the minus and the digits.
Parameter names come from the shared declaration table through that offset;
later consumers need not read their header tokens.

Payload-free choices retain nominal identity while using LLVM `i64` values.
Their type codes are `1000000000 + symbol index`; ordinary records use
`1000 + symbol index`. `recordTypeIndex` recovers either symbol index, and
`typeForSymbol` reads the nominal representation discovered from the normalized
choice declaration before signatures are checked. Both namespaces require a
symbol index below 99000. Semantic record checks include these choices, while
reference ownership checks exclude them. Constructors emit the case tag;
matching and derived capabilities operate on that integer directly.

Lists of these choices use the negative structural List encoding, keeping the
positive List namespace below the nominal choice base. Ordinary containers
without enums retain their existing encodings and nesting capacity. Scalar choice
keys use its otherwise unused low-key codes 0..999: the symbol index is split
into a low remainder and a high quotient, with the quotient packed beside the
zigzag value using radix 99. Only enum-key Maps compact enum value types into
19..99018 and shift other positive children above that range; decoding restores
the nominal identity. Their runtime Map/Set key kind is Integer.

Record-key Maps with a direct enum value use otherwise invalid positive child
residues 32..999 modulo 100000 under Map tags 1, 2, 3, 4 and 7, leaving scalar
codes 19..31 and Lists of those scalar types available. Each bucket contains
968 escape children. The encoder skips the enum-ID bucket; `recordEnumMapPair` reverses this escape. The runtime's nested
Map equality decoder mirrors it. Every two-level record-key Map ending in an
enum fits within signed i64 for all supported nominal indexes. Type encoding
still has a finite nesting limit: extreme enum-containing wrapper chains may
reach it earlier than their former record-valued representation. Ordinary List
type encodings remain compact through 64 layers.

Finite scalar payload niches share the same nominal i64 namespace and Map
codecs. `isScalarChoiceType` describes physical layout; the legacy `isEnumType`
query remains an alias for that physical predicate. Use context-aware
`isPureEnumChoice` for payload-free semantics. `choiceLayoutKind` returns 4 for
a scalar payload niche (storage count 0), alongside 1 for pure enums, 2 for
tagged unions and 3 for nullable record niches. Logical payload fields remain
available; `readChoiceMatchTag` and `readChoiceMatchPayload` project logical
values rather than exposing encoded codes as case ordinals.

`discoverScalarChoiceTypes` runs after all nominal registrations and declaration
index construction, before callbacks or signatures capture numeric IDs. It
updates return IDs and SourceMap nominal IDs together. A linear token scan
collects immutable pure-enum domains; indexed payload lookups then recognize
Boolean, Character and payload-free enum payloads regardless of declaration
order. Nested scalar niches and recursive choices stay boxed in this slice.
No repeated graph rescans or late pointer-to-i64 reclassification occur.

Cached interfaces use `minyar-module-interface-v11` and deltas use
`minyar-module-delta-v9`, so earlier record/enum escape codecs, scalar-choice
and nullable-Set ABI artifacts are rebuilt. This Set ABI revision follows
scalar-choice interface10/delta8.
Choice-bearing module graphs retain whole-program compilation, including when
restored logical choice metadata is the only evidence in a warm state.

`declarations` lists declarations in source order. `symbolNodes[symbol]`
finds their node without a scan. Internal callback environment symbols map
to their closure expression; synthetic symbols without a source declaration
have no node. Literal module initializers get typed literal children, and
runtime initializers get the expressions recorded by their checker.

Compile-time native `register8/16/32/64` layouts retain record syntax nodes
and field children, with runtime type zero. Their compiled symbol kind is 5
(callback signatures use 4); they are excluded from ordinary value/type lookup.
`CompilerContext.registerWidths` is indexed by declaration symbol, and
`registerFields` stores first-bit/width pairs at the ordinary field-table offset.
The contextual `at(first, width)` metadata is consumed by module/generic/header
readers before typed layout validation. Declaration-operand operations emit
scalar IR and never create a runtime record, field-name literal or initializer.

Interrupt contexts use contextual `interrupt function` and header
`handles(vector)`, with the existing modifier feature bit 16. An explicit
`--freestanding --kernel-target x86_64|arm64` selects the compilation context;
module-state compilation is excluded. The handler signature is
`(Integer): Nothing`. The first binding domain is maskable PIC vectors 32..47
or GIC IDs 16..1019. Ordinary identifiers retain their normal lookup rules.

The effects stage audits the complete final module, walks every reached typed
source subtree and parses each reached LLVM definition. Its initial accepted
set is scalar, acyclic code with fixed local storage and resolved direct calls.
Managed values, Float, loops, recursion, indirect/native/runtime calls, mutable
globals, failure paths and unknown instructions reject. Separate internal IRQ
clones omit only proved compiler frame instrumentation; ordinary bodies remain
intact. The clones are parsed and checked again before publication. This proves
context properties, not a physical target stack bound or hardware entry ABI.

The compiler owns one private zeroed 256-byte pending array. Contextual
`signalInterrupt(slot)` emits a release byte store of one; ordinary-context
`takeInterrupt(slot)` exchanges zero with acquire ordering and returns Boolean.
Slots are literal or module-constant Integers in 0..255. Repeated signals
coalesce. These flags carry no event count or DMA ownership permission.

Opaque native record tags `dma_cpu`, `dma_pending` and `dma_queue` keep the
ordinary managed-record pointer ABI. One canonical empty declaration per tag
identifies its resolved source type; these are not Integer/address primitives.
Record construction and unclassified native boundaries reject. Compiler-owned
`dma`/`dma_model` native lowering validates the complete signature before assigning
a borrow or consume rule; user names alone grant no borrowing permission.

`CompilerContext.dma` records declaration kinds, resolved call symbols and source
binding identities separately from LLVM owner slots. Parameters keep logical
ordinals even when immutable parameter lowering substitutes negative LLVM IDs.
The effects stage checks typed source ownership before the IRQ audit. Its first
flow subset admits straight-line statements, if/else and returns with exact
continuing-state joins, normal-exit discharge and an acyclic consuming call graph.
Managed handle reclamation never substitutes for payload ownership/completion.
Resolved direct-call effects exclude DMA from thread/parallel roots, parallel
range bodies and callbacks. Unrelated imported parallel helpers remain valid.

## Node kinds

`syntaxKindName` is the central catalogue. The ranges are registered in the
overnight charter and are separate from lexer and type codes:

- 0: module.
- 1–6: function, record, constant, global, field and parameter.
- 7–10: choice, type alias, test and capability in raw documentation trees. Typed compilation
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

## Choice storage metadata

Choice declarations retain every logical payload field for type checking and
cycle reachability. `choiceLayoutKind(context, type)` identifies an ordinary
type (0), pure enum (1), tagged union (2), nullable managed choice (3), or
scalar payload niche (4).
`choiceStorageCount` reports slots owned by the choice itself; integer and
nullable and scalar choices own no slots. `choiceStorageField` maps a union's logical field to its physical
slot. Debug readers must inspect the layout kind before using an offset.

For nullable choices, `choiceNicheType` identifies the actual managed payload
type, including structural Lists and Sets. The runtime value is a nullable
pointer to that payload's header; readers must not assume record fields.
`choiceNicheTag` gives the non-null case's zero-based tag. The empty case has
the other tag. `readChoiceMatchTag` and `readChoiceMatchPayload` generate the
representation-specific projections, shared by matches and test diagnostics.
Cycle analysis retains the logical graph and projects nullable aliases only
when selecting the runtime ownership entry points. Nullable Set equality delegates
to `minyar_maps_are_equal` with Boolean value kind 4; its null check distinguishes
an absent choice from a present empty Set. Set payloads remain unsupported for
ordering, hashing and key snapshots. Maps retain tagged choice storage.

## Debugger metadata

`debug-types.min` records semantic type graphs in LLVM comments beside initialized
bindings. Each function has its own numeric type namespace, preserved with its
cached code. The debug linker materializes the graph only for debug builds;
release builds keep ordinary executable LLVM. Parameters use their existing SSA
values or stack slots. Small scalarized records use field fragments describing
a virtual aggregate, without introducing stores or allocations.

Lexical markers preserve nested, loop and match-arm scopes. Closure captures and
parameters and outlined worker bindings carry the same descriptions; outlining
regenerates its type graph and invalidates the parent's emission memo. List
storage uses eight-byte slot wrappers whose `value` member has the semantic
element type, preserving Boolean and Character stride. Choice tags retain case
enumerators and payload field names for bounded debugger projections.

Text and Bytes describe their shared runtime prefix. Managed records and Maps
describe their inline storage; arena record/Map pointers, native C-layout
records and callable values currently remain opaque. Optional Python adapters
for LLDB and GDB read these types and inferior memory without evaluating program
code. See the [debugging guide](debugging.md).

## Runtime trace metadata

`runtime-traces.min` records readable names and original token locations while
functions, closures and runtime global initializers are emitted. Each cached module
owns a table of relative string offsets; the final registry is rebuilt from
its current module graph, even on a cache hit. No function address is retained
by a row, so unused functions still disappear during LTO. LLVM `uwtable`
attributes preserve existing unwind descriptions without injected trace calls.

The private runtime ABI uses 40-byte rows (four i32 string offsets, one i32 entry
flag and two i64 source coordinates) and an eight-byte module registry row. Offsets are signed i32
relative to their table and resolved by the static linker. They add no PIE
pointer fixups. Declaration source excerpts are captured at compile time, with
tabs expanded, terminal controls replaced and at most 160 Unicode scalars including
an ellipsis for clipped lines. Missing source text leaves the excerpt empty.
Excerpts remain available after the source is moved or removed; reporting them
adds no source-file reads, runtime allocation or normal-path instructions.
The cold Mach-O reader resolves symbols from loaded __LINKEDIT
and walks ARM64 compact unwind/DWARF CFI. Linux reads ELF symbols only after a
failure and uses the platform unwinder. If symbols or unwind information are
unavailable, the registry supplies an entry location. No C runtime failure is
caught or converted to recoverable control flow by this reporter.

The JSON contract covers explicit compiler diagnostics and source-read errors.
Host failures writing LLVM or cache files still use runtime reports. Hosted Linux currently loads libgcc_s for unwinding; this is a fixed
startup cost, so a strict zero-instruction claim does not apply there.
