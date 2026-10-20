# Real NeoDB manifest recovery under simulated crashes

`make check-simulation-manifests` runs NeoDB's actual `snapshot.min`, WAL and
CRC32C code over the existing in-memory dbio facade. All four production files
are pinned byte for byte to NeoDB commit
`3dd6b03d47e66e5695feefd74603ed2ee0e5a038`; an executable Python 3 SHA-256
check runs before compiling any probe. Snapshot's SHA-256 is
`0d54ab9a5f5725cdc93929ae0db10e894dfc64b333dca1eb5b94e9fa0e6f9c65`.
The only facade addition is `wallClockMicros`, which converts the World's
virtual milliseconds. The program under test uses no host I/O, clock, threads
or native hooks. The ordinary test driver uses host services to compile and
retain evidence, just like the WAL proof.

The success probe runs at O0 and O2 with exact output and the existing runtime
ownership/deferred-cleanup assertions. It calls production `encodeManifest`,
`writeSlot`, `verifySlot`, `openLatest`, `openLatestIn`, `readChunk`, `begin`,
`add` and `finishWal` directly.

- Six durable generations alternate between the two slots. The actual
  simulated background syncer must complete before restart; verification is
  checked both before and after that durability event.
  The other slot retains the preceding generation. Backwards wall-clock jumps
  do not change LSN ordering; timestamps use virtual microseconds.
- 596 crashes cover every prefix boundary, including zero and the full new
  length, for first creation and equal-size, growing and shrinking rewrites.
  First creation durably publishes the name through real `writeSlot`'s
  directory sync. Each recovered file is compared with the complete encoded
  image: recovery selects the new image only when it is complete, otherwise
  selects and reads every chunk of the intact other slot. The fallback is
  reopened independently after rejection.
- 148 explicit corruption controls flip one bit at each encoded byte. Header,
  directory and chunk corruption are rejected. The 12 chunk-byte controls
  preserve valid headers and directories, requiring production `openLatest`
  to verify chunks before selecting a slot. The bad slot remains in place and
  can be durably rewritten and selected on the next restart.
- One real `finishWal` starts with written, unsynced WAL bytes. Its transcript
  must order WAL data sync before the final snapshot header, snapshot data
  sync, rename and directory sync. A subsequent crash recovers the snapshot
  chunks and WAL payload. This covers the completed publication path, not
  every internal interruption of `finishWal`.

Four separate expected-failure programs run at both optimizations: slot write
failure, snapshot LSN beyond the WAL, failed WAL sync during `finishWal`, and
chunk mutation between open and `readChunk`. Each asserts the production exit
status and diagnostic. They are explicit process failures, so the shared
ownership oracle applies to normal success returns rather than failed exits.

The first simulator persists **prefix overlays only**. It does not persist a
truncate separately and never shrinks an existing durable image through
`persistPrefix`. A fully overlaid smaller manifest therefore retains its old
suffix and is rejected until a successful real sync persists the shorter
length. Equal-size overlays can become byte-identical before the final byte
boundary because trailing bytes may be unchanged; the exact-image oracle
handles that case. No claim is made that every incomplete boundary is invalid.
The single-bit controls are explicitly configured corrupt durable images,
not evidence that the simulator explores arbitrary sector persistence.

Directory objects are fixture configuration; name and data durability remain
separate. Syncer switch/stop approximations and limits from the existing WAL
fixture are unchanged. The proof does not cover `slotRetention`, engine
checkpoint scheduling, tables, SQL, the COPY-spill/checkpoint bug, arbitrary
write/truncate/rename interruption, preallocation, recycled segments or real
filesystem guarantees. The `finishWal` check is at the WAL-bytes boundary.

On failure, retain the directory printed as `Manifest proof evidence:` and
the outer build log. It contains pinned fixture copies, per-case sources,
LLVM and compile/link/run stdout/stderr; O0 and O2 use distinct case numbers.
Assertion failures also print the World's transcript and the failing prefix
or byte index. The directory is removed only after every oracle passes.
`make check-simulation-manifests-sanitize` provides the corresponding optional
ASan/UBSan compiler/runtime run.

Run `check-simulation-neodb` alongside this target when changing the shared
facade, so the WAL recovery and syncer contracts remain independently checked.
