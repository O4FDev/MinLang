# Incremental module builds

Use `--incremental` to reuse checked module interfaces and LLVM code between
builds of the same entry file:

```sh
./minyar --incremental tests/modules/basic/main.min -o module-example
./minyar --incremental --release tests/modules/basic/main.min -o module-example
```

Small programs and first builds can take longer. Clang still generates and
links the native program on every invocation; release mode retains whole-program LTO.

The cache defaults to `build/module-cache`. Set `MINYAR_MODULE_CACHE` to choose
another directory. It is disposable: `make clean` removes the default cache.
Compiler images for distinct compiler versions are retained until the cache is
cleared. Cache artifacts are local implementation details, not a package format
or an interchange format for downloads. Individual artifacts are capped at
64 MiB; larger results still compile but are not persisted for reuse.

## What is reused

Every build reads the reachable source files and compares their complete
contents. An unchanged module loads its saved imports and checked code without
lexing, parsing, type checking, or generating its function bodies again.

A body-only edit normally recompiles that module. Its callers can retain their
checked code if their imported interfaces still match. An interface includes
function signatures, public visibility, record field names/order/types, and
private or recursive record types reachable through those signatures. Relevant
interface changes invalidate consumers; unrelated modules remain reusable.

An exact graph-interface match also reuses the compiler's checked declaration
and type tables. Interface changes rebuild those tables. Consequently, interface
edits save less work than body edits even when few function bodies change.
Missing dependencies, import cycles, and invalid source are still errors.
Diagnostics retain the original source filenames and line numbers.

## Identity and publication

Artifacts belong to one canonical entry path, one exact compiler binary and
one effective ownership policy. The launcher forwards the selected cleanup
budget. K1 uses ordinary code; other budgets key stack ownership by the useful
limit `min(8, K−1)`. Both base and delta envelopes must match that policy.
Source changes with unchanged timestamps are detected. The driver compares
compiler bytes rather than trusting modification times. Code names are stable
within the entry's namespace: modules below its directory use relative paths,
and outside modules use separately tagged absolute paths. Import traversal order
does not determine those names. Artifacts are not shared across entry files.

A base file holds a complete successful frontend result. Small edits publish a
separate delta relative to that immutable base. Successive deltas describe all
current differences from the base; they do not form a chain. When more than
half the current modules differ, publication compacts to a new base. A delta
from a different base generation is ignored.

The native driver validates the entry, compiler, envelope format and integrity
before use. Its checksum detects accidental corruption; it is not authentication
for remotely supplied files. Invalid state falls back to a clean frontend build.
Compiler images are published under immutable names and verified against the
requested compiler bytes. Per-invocation files and atomic replacement prevent
concurrent builds from exposing partially written output or combining different
base generations. Serialize the initial compiler/runtime bootstrap and builds targeting the same
output executable. A failed frontend build preserves earlier successful output
and cache state. A later Clang failure can leave a valid frontend cache, since
Clang flags and module native objects are not cached. The configured standard
runtime is cached separately by its Makefile dependencies.

Publication uses atomic filesystem operations, without durability synchronization.
An interrupted or crashed process can leave temporary files; partial or missing
artifacts can be discarded on a later build. Do not edit source files or cache
files concurrently with a build when requiring a coherent source snapshot.

## Validation and current limits

```sh
make check-incremental-modules
make check-incremental-modules-sanitize
make check-incremental-module-performance
python3 tests/incremental-module-performance.py --link --sizes 400 --shapes wide
python3 tests/incremental-module-memory.py
```

The normal `make check` includes incremental correctness and frontend performance
checks. Run the sanitizer target separately to check generated compiler LLVM and
the native driver.

The incremental driver has been tested on macOS ARM64 and through ownership
policy/cache-edit checks on Linux ARM64 and x86-64. The Linux runs used a local
VM, with x86-64 instruction translation; they establish selected correctness,
not native deployment performance. Windows is unsupported.
