# Production neo-db engine fixture

The 72 pinned files are copies of the local neo-db repository at
`8df7c7a1edc8537ab1a91cc3693e652034e5a278` (branch `nd-merge`: run-20261025 with the run-2 branches merged, D8). The 58 files under `src/`
and the 13 sources of the `neodb-sdk`, `vector`, `uuid-ossp` and `feed-redact`
packages under `sdk/` and `extensions/` are the complete transitive local
import graph of `src/engine/api.min`; the four package manifests are pinned
too. Every file is byte-for-byte production source except `src/engine/zcodec.min`, which is neo-db's own
deterministic stand-in `tests/search/sim/zcodec.min` at the same revision (the production codec calls native
zstd; the stand-in never compresses, as in neo-db's `tests/search/sim.sh`). The sources hold
82,570 lines/2,893,232 bytes; their standard-library imports are `boundary`, `math`, `text`. `source-pins.json` records every SHA-256
and the revision. The host harness verifies each file before copying it into
retained test evidence.

`lib/dbio.min` is a test-only deterministic I/O facade copied from the smaller
WAL/snapshot simulation fixture. Its additional engine boundary consists of a
no-op `init`, pure virtual `monotonicNanos`, `preadAppend`, `randomBytes`
drawn from the World's decisions (SQL `random()` and UUIDs), a no-op
`releaseFreeMemory`, and `parallelWorkers` = 1 (safe parallel ranges run on one thread). It uses no host
files, clocks, sockets or worker threads. Actual engine/parser/transaction,
checkpoint, table-image and recovery algorithms remain production source.

The labeled negative control changes only `checkpointBlocked` in a temporary
copy after verifying all original pins. It restores the historical omitted
guard, so the same public SQL/COPY scenario must fail at its recovered-data
oracle. The vendored production source is never modified by that control.

Run the separate `check-simulation-engine-compile` target before the full
`check-simulation-engine`; the full 50k-line engine is intentionally outside
portable smoke checks. See [the model and coverage](../../../docs/simulation-engine.md).
