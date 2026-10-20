# Production neo-db engine fixture

The 27 files under `src/` are byte-for-byte copies of the local neo-db repository
at `3dd6b03d47e66e5695feefd74603ed2ee0e5a038`. They are the complete transitive
local import graph of `src/engine/api.min`: engine, SQL and storage. The graph
contains 37,218 lines/1,291,846 bytes; `math` is its only standard-library import.
`source-pins.json` records every production SHA-256 and the revision. The host
harness verifies each file before copying it into retained test evidence.

`lib/dbio.min` is a test-only deterministic I/O facade copied from the smaller
WAL/snapshot simulation fixture. Its additional engine boundary consists of a
no-op `init`, pure virtual `monotonicNanos`, and `preadAppend`. It uses no host
files, clocks, sockets or worker threads. Actual engine/parser/transaction,
checkpoint, table-image and recovery algorithms remain production source.

The labeled negative control changes only `checkpointBlocked` in a temporary
copy after verifying all original pins. It restores the historical omitted
guard, so the same public SQL/COPY scenario must fail at its recovered-data
oracle. The vendored production source is never modified by that control.

Run the separate `check-simulation-engine-compile` target before the full
`check-simulation-engine`; the full 37k-line engine is intentionally outside
portable smoke checks. See [the model and coverage](../../../docs/simulation-engine.md).
