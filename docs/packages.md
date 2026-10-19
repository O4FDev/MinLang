# Packages

A package is a `Minyar.toml` and a source library. Its Git repository can live on
any HTTPS Git host. Import the package by its manifest name:

```sh
minyar add github.com/O4FDev/paint
```

```minyar
use "paint" as paint
```

The repository needs `src/<package-name>.min` and a three-part package version.
Relative imports inside the package work normally. Git packages may depend on
other Git packages; editable local projects may also use path dependencies.

## Choose a version

```sh
minyar add github.com/O4FDev/paint          # highest stable semver tag
minyar add github.com/O4FDev/paint@v0.1.0   # release minimum
minyar add github.com/O4FDev/paint@main     # pin the current branch commit
minyar add github.com/O4FDev/paint@COMMIT   # full SHA or unambiguous prefix
```

`https://` and a trailing `.git` are optional. SSH, credentials in URLs, custom
transport commands, prerelease version ranges and repository subdirectories are
not supported. Public HTTPS repositories are the initial transport contract.
If there are no stable tags, choose a branch or commit explicitly.
Full 40-character commit IDs always name objects, even if a repository creates a
tag with the same name. Unambiguous object prefixes also take precedence over
similarly named refs. Locked exact IDs must match their recorded commits. A
missing pinned commit is fetched directly when the host permits it; ordinary
advertised-history fetching remains a fallback for hosts that restrict SHA wants.

`add` writes a source declaration and pins the resolved graph:

```toml
[dependencies]
paint = { git = "github.com/O4FDev/paint", rev = "v0.1.0" }
```

Versions are compared numerically. When two dependencies request `v0.1.0` and
`v0.2.0`, the graph selects `v0.2.0`, without upgrading to an unrequested release.
A compatible lock is the starting build list. Different major versions, different
repositories with the same package name, and differing branch/commit selectors
are conflicts. Minyar prints the conflicting requests. There is one shared name
namespace, so use one major version or branch throughout a graph. Tag versions
must agree with `package.version`. This is minimal version selection within one
major, not a solver for arbitrary version ranges or a semantic compatibility
proof. Version zero follows the same major rule; authors must manage its API
compatibility deliberately.

Ordinary builds retain exact commits from the lock, even when a branch moves.
Repeat `add ...@main` to deliberately refresh a branch. Repeat a bare `add` to
discover the latest release. Locked tags remain immutable in the local cache.
Discovery is reused throughout the same `add`, including branch pins; it does
not download the same source again during graph resolution. A discovered stable
release is also cached under its tag for later offline additions. If a host moves
an already cached release tag, fresh latest discovery rejects the changed release.
Edits to a Git dependency graph update its lock immediately, including removing
its final Git source or adding/removing a local wrapper around Git dependencies.
The result is ready for `--locked --offline`. Local-only path dependencies remain
editable and retain their existing graph-lock behavior. `add` and `remove`
rewrite supported manifest fields and comments.

## Reproduce a build

Commit `Minyar.toml` and `Minyar.lock`. The latter records the Git host path,
selector, full commit, manifest hash and SHA-256 of every exported source file.
It never records a machine's global cache path.

```sh
minyar build --locked             # exact graph; fetch missing pinned sources
minyar build --locked --offline   # exact graph; cache only
minyar tree --locked --offline
minyar metadata --locked --offline
```

Both locked and ordinary resolutions verify all cached package files. A modified
or incomplete entry fails with its cache location; it is never silently repaired
or accepted. Restore the entry from a trusted source, or remove that one entry
and fetch the locked commit again. Local source edits do not change a path
dependency's graph lock. Remote source edits always fail checksum verification.

## Cache format

The store is `$MINYAR_HOME/packages` or `~/.minyar/packages`:

```text
packages/
  sha256/<64-hex-digest>/  source tree, without .git
  refs/<64-hex-digest>    local selector → commit/checksum/revision hint
```

The source checksum is SHA-256 over UTF-8 `minyar-source-v1\n`, followed by one
record per regular file, sorted lexicographically by UTF-8 path bytes:
`<sha256-of-file> <JSON-quoted-relative-path>\n`. JSON quoting is compact and
preserves Unicode. File contents and path names participate; timestamps, empty
directories and executable permission bits do not. Downloaded files are source
data and are never made executable. Every blob is included, including docs and
tests; Git attributes do not alter exports. Cache references are hints, while a
committed lock is the project's trust record. Concurrent downloads stage in
private directories and publish only complete verified trees.

The lock detects changes after the first trusted resolution. It does not prove
an author's identity, establish a globally witnessed history, or make dependency
code safe to execute. Review changes to both the manifest and the lock.

## Source policy

Downloads use a fresh bare repository with no checkout, inherited Git
configuration, credential helper or hooks. Files are read directly from Git
blobs. Git submodules, symlinks, absolute paths, `..` path components, Git
metadata paths, backslashes, control characters and colon-bearing paths are
rejected. Packages are limited to 16,384 files, 128 MiB of source data and 4,096
nested text/interpolation contexts. The native-keyword check follows flat block
comments and ordinary, raw and multiline text; interpolation contents are code.

Packages never run install/build scripts. Remote dependencies cannot contain
native C, Objective-C, Swift, assembly or binary implementations, or declare a
Minyar `native` function. They may import the toolchain's standard modules.
Remote manifests cannot escape the pinned graph with local path dependencies.
Relative source imports must stay inside their own content-hashed tree; shared
files beside `src` are allowed. Module paths use single-line ordinary or raw
Text literals. Ordinary escapes are decoded before checking the path; absolute
paths, backslash separators and traversal outside the tree are rejected.
Multiline Text remains available for data, while package import paths stay on
one line. These checks also run when verifying an existing cached tree.
Native integrations remain an explicit application/toolchain responsibility.
This policy concerns installation and compilation; running an imported Minyar
program can still perform I/O, including from global initializers.

## Test an unpublished repository

No network access is needed to exercise the exact GitHub package path. Set a
process-scoped mirror directory containing bare repositories:

```text
mirror/github.com/O4FDev/paint.git
```

```sh
MINYAR_GIT_MIRROR=/absolute/path/to/mirror \
  minyar add github.com/O4FDev/paint
```

The repository path written to the manifest and lock remains `github.com/...`.
Only the fetch location changes. No global Git configuration is modified.
`make check-package-git` uses private mirrors and caches to test release ordering,
tag/commit/branch pins, transitive minimal version selection, real O0/O2 builds,
offline use, relocation, source tampering and unsafe package rejection.

The [first light gallery project](../examples/gallery/paint/README.md) installs
the real external `paint` library through this route and renders PNG and SVG.
Its separate repository includes paths, antialiasing, gradients, TrueType text,
three reproducible artworks and a local `v0.1.0` tag. Before publication, use the
documented private mirror. `make check-paint-package MINYAR_PAINT_SOURCE=/path/to/minyar-paint`
tests the complete offline debug/release workflow without adding the external
library to Minyar's core or relying on GitHub.
