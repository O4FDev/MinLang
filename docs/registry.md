# A package index you can host

The package index is static JSON. The checksum database is a canonical text file
and a SHA-256 root embedded in the index. Both can be served from any HTTPS static
host, alongside the installer and release artifacts. There is no public Minyar
registry deployed yet.

## Prepare a package record

Commit a source library and tag its exact version, for example `v0.1.0`.
From that repository root:

```sh
mkdir -p ../release-records
minyar publish github.com/O4FDev/paint --dry-run \
  --description "A small vector studio for paths, light and Minyar." \
  > ../release-records/paint-0.1.0.json
```

`publish` is always a dry run in this version, including when `--dry-run` is
omitted. It requires a clean Git tree, a library export and a version tag at HEAD.
It reads committed blobs, applies the source security policy and emits metadata.
It does not upload, create a repository, change remotes or execute package code.
Keep redirected output outside the package so it does not make the tree dirty.

```sh
minyar registry build ../release-records ./public
minyar registry serve ./public 8080
```

The builder merges records with an existing index. A published
`repository@version` record is immutable, and rebuilding identical input is
deterministic. The server binds loopback only and accepts GET/HEAD. It serves
`index.json`, `checksums.txt`, `install` and files below `releases/`; traversal and
symlink escapes fail. It accepts no uploads. Its per-response limit is 16 MiB,
suited to index development and small installer fixtures. Serve full LLVM
toolchain archives directly from a static host with appropriate large-file limits.

The standalone server is `build/tooling/tools/registry-cli`, built with
`make build/tooling/tools/registry-cli`. Copy that binary and a prepared public
directory to a matching host and run `registry-cli serve /srv/minyar/public 8080`
under an ordinary process supervisor. Put an HTTPS reverse proxy or static file
server in front of it. Keep signing keys, source repositories and operator state
outside the public directory. No deployment is performed by these tools.

## Discover and verify

```sh
export MINYAR_REGISTRY=https://YOUR-HOST
minyar search paint
minyar info paint
minyar add github.com/O4FDev/paint
minyar build --locked --offline
```

`--registry URL_OR_DIRECTORY` selects an index for `search` and `info` without
changing the environment. A local public directory also works. HTTP is allowed
only for loopback testing. Search folds ASCII case and searches names, repository
paths and descriptions; it displays the highest stable version of each repository.

When `MINYAR_REGISTRY` is configured, Git release commits and content hashes must
match its records. Branch/commit selectors still use the project's exact lock and
do not claim to be registered releases. The default Git workflow needs no registry.
Remote indexes are cached under the global package store. `--offline` uses the
cached index and source trees and never contacts a host. Clients retain a local
witness: a later index cannot remove or change previously seen release records.

An index has schema 1, a packages array, and a checksum root. Each release record
contains name, repository, version, description, commit and checksum. Source
checksums use the [package source-tree format](packages.md). `checksums.txt` begins
with `minyar-checksums-v1\n`, followed by records sorted by
`repository + "@" + version`, each as:

```text
REPOSITORY VERSION COMMIT SOURCE_SHA256
```

The checksum root is SHA-256 over those exact UTF-8 bytes, including the header
and final newlines. The index is limited to 4 MiB and 10,000 releases. Duplicate
records, duplicate JSON keys, malformed commits/checksums and a wrong root are
rejected. This is a small checksum database with local append-only witnessing;
it is not a globally witnessed Merkle log or proof of publisher identity. Initial
trust comes from the configured HTTPS host or local index, plus reviewed locks.

## Test without the internet

`make check-registry` creates local source/bare repositories, generates dry-run
records and checksums, runs the real Minyar server on an ephemeral loopback port,
and tests discovery, Git source verification, offline index reuse, mutation
rejection, HTTP methods and path policy. Neither GitHub nor a hosted registry is
required. See [installation](install.md) to prepare signed toolchain artifacts in
the same public layout.
