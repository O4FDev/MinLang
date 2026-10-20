# NeoDB storage with typed kernel completions

This strict Linux integration compiles the actual, unchanged NeoDB WAL,
CRC32C, utility and snapshot modules against a test-only host-file facade.
Asynchronous sync requests use public `completionio.Queue.sync`, `submit`
and typed CQ collection against real Linux `io_uring`. There is no mock or
native background-syncer fallback. A separate provider exercise uses actual
typed READ, WRITE and FSYNC operations and verifies their results.

Status at source handoff: **not compiled or executed**. These are test
definitions, not a claim of a passing integration. Parent qualification must
run the commands below on an authorized Linux box.

The production source is vendored from NeoDB commit
`3dd6b03d47e66e5695feefd74603ed2ee0e5a038`, as recorded in
[the original fixture provenance](../tests/fixtures/neodb-simulation/README.md).
Before compilation the host harness checks lengths and SHA-256 hashes, then
copies these exact bytes into a private temporary fixture:

| Module under `src/storage/` | Bytes | SHA-256 |
| --- | ---: | --- |
| `wal.min` | 32022 | `1dc0de2a4cc00e6c6490686dd14b1b0f704142cf5baab5c497b8a8cc4be2635b` |
| `crc32c.min` | 2280 | `585a6697149eb7dd2ac828eb734dbc73841bcff4313fe23f44c4ae3c8f6514b1` |
| `util.min` | 2902 | `db3a95e5e7b00dbdebed389a6afbc7fcd5a831984de00cb3aff5ef2ac458f04d` |
| `snapshot.min` | 22273 | `0d54ab9a5f5725cdc93929ae0db10e894dfc64b333dca1eb5b94e9fa0e6f9c65` |

The shape is `fixtures/neodb-completion/src/storage/{wal,crc32c,util,snapshot}.min`
and `fixtures/neodb-completion/lib/dbio.min`. The probe imports the staged
production modules; their own `../../lib/dbio.min` imports select the new
facade. Production imports, declarations, framing, recovery and snapshot code
are untouched. The original simulator facade is not copied or linked.

`tests/completionio-neodb.min` uses `frontend-fixtures` to compile and run
separate O0/O2 programs with exact output and ownership assertions. It links
`runtime/native/completionio.c`, `files.c`, `system.c` and `-pthread` explicitly.
The host writes `provenance.json` with production pins, the kernel release and
hashes of facade/probe/public-library/provider inputs. That manifest describes
inputs; the successful fixture assertions establish execution evidence.

The selected standalone contract has deliberate boundaries:

- Ordinary WAL positioned writes and snapshot sequential/positioned writes use
  `files.writeAt`/`files.write`, preserving production dbio's all-or-error
  behavior. A potentially short asynchronous WRITE does not replace them.
- Each syncer owns a typed ring with eight outstanding entries and no byte
  buffers. A request stages a real FSYNC with IO_DRAIN, records its operation
  ID, token and logical `upTo`, and submits with finite EINTR/partial-submit
  retries. Querying requested/durable state does not collect CQEs. This test
  facade retains request-history metadata for the run; its memory grows with
  total requests even though kernel owners stay bounded by eight per ring.
- Explicit `progress`, `completeNext`, `syncerDrain` or blocking `syncerWait`
  collects results. Acknowledgement requires matching ID/token/kind, zero sync
  count and a contiguous prefix of checked request completions. The first
  error is sticky; subsequent collection cannot advance that syncer's offset.
- Facade descriptors never reuse handles. Caller close drops its reference;
  the syncer retains the same open file description without reopening by name.
  The provider separately duplicates each queued fd. Switch waits for the old
  file's boundary before releasing its reference. Stop drains all operations,
  including after a failed CQE, closes the ring and releases the last fd.
- Directories must be registered through facade `mkdir`. NeoDB's initial lazy
  syncer retains a directory placeholder. Its first switch selects the regular
  segment without advancing requested/durable offsets, including after a
  checkpoint with a nonzero LSN. That directory contains no WAL bytes; the
  production caller already synced namespace publication. No directory sync is
  submitted to this regular-file provider and no synchronous syncer fallback
  runs. Subsequent regular-file switches keep the blocking durability rule.
- `syncerNotifyFd` returns `-1` explicitly. There is no notification socket,
  event-loop integration or full NeoDB engine adapter. `completeNext` scans
  rings in facade order and makes no cross-ring scheduling claim.
- Positive `syncerWait` timeouts return `-95` (ENOTSUP); zero checks the current
  acknowledged state without collecting and returns `-110` when unfinished.
  `-1` drives explicit blocking kernel collection with finite retry counts and
  the host process deadline. Permanent submission/collection failures fail the
  fixture while retaining owners that cannot safely be freed.
- Production's explicitly synchronous reopen/file-publication and directory
  sync calls still use `files`. They are not a fallback for `syncerRequest`.
  Preallocation, recycling and a notification reactor remain outside this
  integration; options select no preallocation and no recycled segments.

The probe asserts exact empty/slice/builder/batched records, separate appended,
written and acknowledged LSNs, no acknowledgement before CQ collection and the
production callback, CRC/LSN validation on reopen, 128 records through 64 tiny
segment rotations, and correct cleanup of reader/writer/syncer descriptors.
It checks a pending sync across caller close, old-file switch durability,
zero/unsupported timeout behavior, idempotent requests and stale stop handles.
A procfs regular file supplies real failing FSYNC CQEs (required EINVAL),
which must stay sticky through wait and drain/stop. Linux procfs must be mounted.
Missing permission for IO_DRAIN instead produces EACCES and fails the proof.

The production `snapshot.finishWal` check starts with an outstanding WAL sync,
requires that sync's successful CQE before publication, verifies snapshot
header/directory/chunk CRCs (including an empty chunk), closes after checkpoint,
and reopens a new WAL at the snapshot LSN. A separate deliberate payload
corruption control confirms that production CRC checking rejects bad bytes.

After parent authorization and box lease, run from the isolated source worktree:

```sh
BX_TIMEOUT=900 '/Users/luke/Projects/minyar-moonshots-20261020/bx' systems make -j8 check-completionio-neodb-kernel
BX_TIMEOUT=1200 '/Users/luke/Projects/minyar-moonshots-20261020/bx' systems make -j8 check-completionio-neodb-sanitize
```

Both targets require the existing strict `check-completionio-kernel` first,
including its dedicated C probe and typed API/gallery proof. Neither target is
part of portable/default checks. Unsupported rings, exit 77, forbidden setup,
restriction errors, wrong CQE counts and hangs are failures, never skips.
The sanitizer target also runs that same C kernel probe with ASan/UBSan/LSan,
then uses the sanitized compiler and instruments the generated program/runtime
at O0/O2 with managed ownership checks. Managed-fixture leak detection follows
the existing sanitizer convention (`detect_leaks=0`); native C leak checking
uses `NATIVE_SANITIZER_ENV`.

The harness caps each generated execution at 30 seconds, compilation at 120
seconds, and provider submission/collection retries at 64. Ownership runtime
build/link deadlines come from `frontend-fixtures` (30 seconds). The existing
test timeout scale applies. Strict targets retain the printed evidence directory
on success as well as failure; it contains copies, provenance, per-optimization
LLVM/runtime/executable and compile/link/run logs. Preserve it with the box run
log before a rerun or cleanup. Direct host-harness invocation removes successful
evidence unless `MINYAR_NEODB_COMPLETION_KEEP=1` is set.

This is a real-kernel completion, persistence-call ordering and storage-format
integration check. A reopen through the host page cache or a process restart
does not prove power-loss safety. Keep the separate deterministic simulator
crash proofs (`check-simulation-neodb`, `check-simulation-manifests`) as separate
evidence. No simulator-to-kernel performance ratio is claimed or meaningful
here, and no throughput measurement is included.
