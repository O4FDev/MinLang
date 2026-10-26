# Production neo-db engine fixture

The 48 pinned files are byte-for-byte copies of the local neo-db repository at
`f4a90a1f527e8b2f5d700251cc06ae8bf24e8071` (branch `search2-20261025`: the
search engine with its multi-core kernels). The 36 files under `src/` and the
eight sources of the `neodb-sdk`, `vector`, `uuid-ossp` and `feed-redact`
packages under `sdk/` and `extensions/` are the complete transitive local
import graph of `src/engine/api.min`; the four package manifests are pinned
too. The sources hold 49,701 lines/1,722,346 bytes; `math` is their only
standard-library import. `source-pins.json` records every production SHA-256
and the revision. The host harness verifies each file before copying it into
retained test evidence.

`lib/dbio.min` is a test-only deterministic I/O facade copied from the smaller
WAL/snapshot simulation fixture. Its additional engine boundary consists of a
no-op `init`, pure virtual `monotonicNanos`, `preadAppend`, `randomBytes`
drawn from the World's decisions (SQL `random()` and UUIDs), and a no-op
`releaseFreeMemory`. It uses no host
files, clocks, sockets or worker threads. Actual engine/parser/transaction,
checkpoint, table-image and recovery algorithms remain production source.

The labeled negative control changes only `checkpointBlocked` in a temporary
copy after verifying all original pins. It restores the historical omitted
guard, so the same public SQL/COPY scenario must fail at its recovered-data
oracle. The vendored production source is never modified by that control.

Run the separate `check-simulation-engine-compile` target before the full
`check-simulation-engine`; the full 50k-line engine is intentionally outside
portable smoke checks. See [the model and coverage](../../../docs/simulation-engine.md).
