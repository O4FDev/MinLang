# NeoDB WAL simulation fixture

Vendored unchanged from `/Users/luke/Projects/neo-db` at commit `3dd6b03d47e66e5695feefd74603ed2ee0e5a038`.
Only `lib/dbio.min` is the simulation adapter; production storage code is unmodified.

| Path | Bytes | SHA-256 |
| --- | ---: | --- |
| `src/storage/wal.min` | 32022 | `1dc0de2a4cc00e6c6490686dd14b1b0f704142cf5baab5c497b8a8cc4be2635b` |
| `src/storage/crc32c.min` | 2280 | `585a6697149eb7dd2ac828eb734dbc73841bcff4313fe23f44c4ae3c8f6514b1` |
| `src/storage/util.min` | 2902 | `db3a95e5e7b00dbdebed389a6afbc7fcd5a831984de00cb3aff5ef2ac458f04d` |

`tests/simulation-neodb.min` verifies these hashes before compiling or executing
the fixture. Its Python 3 check uses only the standard library.

The adapter owns one World's completion stream, submits actual asynchronous
sync operations, and advances them only through `simulation.next`. Crash drops
process descriptors and queued work through `dbio.crash`. Configured directory
objects persist; directory entries and file bytes obey simulation's separate
durability rules. There are no host files, clocks, threads or sockets in the
program under test; `syncerNotifyFd` returns -1.

The production syncer's asynchronous switch queue is approximated by a blocking
switch after the previous file is durable. Stop drains pending requests. Both
preserve the required durability ordering and sticky error behavior. General
switch latency, notification readiness, preallocation and recycled segments are
outside this fixture's coverage. Tests select 64-byte segments, no preallocation
and zero recycled files, and keep the maximum simultaneous sync batch at two.

The success program runs with exact output and ownership cleanup assertions at
O0 and O2. Separate O0/O2 failure programs assert the production WAL's refusal
of failed fdatasync and corruption in a non-final durable segment.
