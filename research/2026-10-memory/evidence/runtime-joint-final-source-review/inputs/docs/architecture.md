# Compiler organization and development standards

Minyar separates language implementation, runtime policy, standard libraries,
tools, and executable examples. The layout follows the responsibility boundaries
used by [Rust's compiler workspace](https://rustc-dev-guide.rust-lang.org/compiler-src.html)
and [Swift's compiler](https://www.swift.org/documentation/swift-compiler/), scaled
to this repository's self-hosting bootstrap.

| Directory | Responsibility |
| --- | --- |
| `compiler/` | Self-hosted compiler and incremental module frontend. |
| `bootstrap/` | The deliberately smaller C stage-zero compiler. |
| `runtime/` | Runtime ABI, Text, ownership, allocation, collections, Bytes, numeric operations. |
| `runtime/native/` | Native implementations of standard-library packages. |
| `library/` | Public Minyar package interfaces. |
| `tools/` | Public build-driver support and native compiler invocation. |
| `build-support/` | Separate compiler, runtime, examples, checks, and research Make rules. |
| `scripts/` | Developer tooling, coverage collection, and platform validation. |
| `tests/` | Harnesses, conformance, exact diagnostics, model tests, mutation, fuzzing, and performance. |
| `examples/` | Language examples and Minyarcraft; no compiler/runtime dependencies point here. |
| `experiments/` | Reproducible measurements and maintained independent reference models. |
| `build/` | Disposable binaries, IR, caches, and retained test evidence. |

`Makefile` defines the default configuration and includes the named build-rule
files. Keep artifact recipes out of the check recipes. All runtime implementation
headers are dependencies, including fragments used only by a particular profile.
A compiler/flag identity stamp invalidates native artifacts when tools change;
warm probes leave its timestamp unchanged.

## Runtime boundaries

`minyar_runtime.c` is the one translation unit and owns common types, allocation,
Text, process arguments, and text I/O. It includes the following private
implementation fragments:

- `minyar_collections.h`: Lists and records.
- `minyar_numbers.h`: checked numeric operations, conversions, and Float text.
- `minyar_bytes.h`: packed buffers, endian access, binary I/O, and native extension.
- `minyar_rc.h`, `minyar_bounded_rc.h`: ownership and scheduled reclamation.
- `minyar_heap.h`, `minyar_pool.h`: allocator selection and finite pools.

These fragments are not independent public headers. Keeping one translation unit
preserves private state and optimization across the runtime without exporting a
new ABI. The module compiler adapter is similarly checked against its exact
source context: failed adaptation must stop the build.

Generated LLVM contains small internal List access helpers so ordinary builds
can optimize checked reads, scalar writes, and length loads without LTO. Their
layout dependency is explicit and guarded by C static assertions. Invalid
positions use the existing runtime diagnostic path. Reference writes continue
through the ownership runtime; the emitter adds no aliasing promises. Tests
exercise reallocation and receiver replacement during index/RHS evaluation.

Checked scalar operations likewise expose their successful paths in LLVM.
Integer overflow and division failures use explicit cold, non-returning runtime
entry points; the older checking ABI remains available to bootstrap and native
callers. Other scalar helpers retain returning runtime fallbacks on invalid
inputs. An optimizer assumption must follow the declared ABI, including whether
a fallback can return.

## Language and native linkage

Generated language functions use the `.minyar.fn.` LLVM namespace. This keeps
ordinary names such as `malloc`, `printf`, or `minyar_rc_enter` separate from the
runtime and native libraries. The executable entry keeps the platform's `main`
ABI; explicit native declarations keep their declared C symbols. Source names
therefore need no blacklist of present or future runtime functions. Native
bindings are checked against the complete emitted runtime declaration catalog,
including bounded-owner declarations and cold failure paths. A matching native
signature still cannot repurpose a runtime-owned symbol.

The incremental frontend uses stable module identities inside that namespace.
Interface schema v5 and delta schema v3 invalidate cached bodies from the prior
linkage ABI. C fixtures that inspect compiler internals use the shared
`tests/llvm_symbols.h` alias helper, including the target's symbol prefix; this
is a testing interface, not a public foreign-function ABI.

## Formatting and source review

`.editorconfig` defines four-space indentation and LF line endings. C formatting
uses `.clang-format`, based on the [LLVM style used by Swift's compiler](https://github.com/swiftlang/swift/blob/main/.clang-format),
with the existing four-space indentation and a 100-column ceiling. These choices
also match [Rust's documented indentation and line-length conventions](https://rustc-dev-guide.rust-lang.org/conventions.html).
Use ClangFormat 23.1.2 for reproducible formatting of the bootstrap compiler, native module driver, extracted runtime
fragments and new C tests; `make check-format` checks that maintained set, and CI
installs the [pinned formatter package](https://pypi.org/project/clang-format/23.1.2/)
to enforce the same result.

Formatting must preserve diagnostic locations, literal bytes, generated source,
and mutation anchors. Existing golden fixtures and bootstrap-sensitive Minyar
source are excluded from automatic C formatting. Production sources are migrated
by responsibility, with tests, rather than applying a formatter for a different
language to `.min` files. Generated LLVM and vendor code are not hand-formatted.

Minyar declarations and functions keep four spaces, braces on the same line,
descriptive names, and one logical operation per statement. Prefer early returns
where they expose the invariant. Write comments explaining proof obligations,
ownership, or complexity; do not narrate obvious statements. New runtime fast
paths need a measured workload and an independent semantic or work-bound oracle.

## Bootstrap constraint

Token locations use a typed `SourceMap`: full-width Integer coordinates, shared
module paths, and sparse origins for persisted interfaces. Each lexical token
stores a line/column pair; a separate lazy path-index list leaves ordinary
single-file tokens at their implicit default path without storing zero for each
token. Imported tokens can fill gaps and assign paths without narrowing any
coordinate. Formatting a location
is diagnostic work, rather than an allocation for every successful token or
expression. The bootstrap supports the typed record construction and field
access required by this representation. Tests check both large coordinates and
the number of location conversions during successful compilation.

The ordinary compiler is still one self-hosted source unit: its parser, type
checking, ownership decisions, and LLVM emission share state. Relocating that
unit does not make those phases independent. A future split must first introduce
explicit typed representations and stable interfaces, then preserve both the
stage-two/stage-three fixed point and compile-time budgets. Concatenated copies
of the same implementation are not separate maintained sources.

See [testing](testing.md), [performance](performance.md), and the
[syntax review](syntax-review.md) for the corresponding acceptance criteria.
