# Actual engine checkpoint recovery

`make check-simulation-engine` runs the unmodified neo-db engine, SQL parser,
transactions, table images, checkpoint publisher and recovery through explicit
deterministic I/O. The fixture pins all 27 production modules to revision
`3dd6b03d47e66e5695feefd74603ed2ee0e5a038`; hashes are checked before compilation.
This opt-in target is larger than the WAL and manifest unit integrations.
`make check-simulation-engine-compile` isolates source compilation first.

The public engine API creates a table, performs COPY with 80 rows of 65,536-byte
text, and verifies an actual `P` WAL record crossed the unchanged 4 MiB redo
spill threshold. A second session requests CHECKPOINT while COPY remains active.
The test drives public checkpoint phases and simulated sync completions, completes COPY,
waits for the returned commit LSN to become durable, then discards volatile state
without calling clean shutdown or advancing another checkpoint. Reopening the
production engine must recover all rows, their identifier sum and exact payloads.
An independent unfinished COPY scenario must recover zero rows despite durable
partial redo records.

A labeled control copies the verified engine into temporary evidence and omits
only its active-spill checkpoint guard. It executes the same scenario and must
fail specifically because acknowledged rows are missing after recovery. A changed
guard return value alone does not satisfy that control. The production fixture
remains unchanged; this reproduces a historical regression mechanism rather than
claiming a current upstream defect.

Normal scenarios run at O0/O2 with the shared exact managed-ownership oracle.
The deliberately failing control asserts its exit and diagnostic without an
unwind-cleanup claim. `check-simulation-engine-sanitize` uses compiler/runtime and
generated-program ASan/UBSan. The retained evidence path includes source pins,
the original and control source, LLVM, compiler/link logs and run output.

The host explicitly drives cooperative API-call and completion boundaries. This
does not enumerate every write inside a call, native thread interleavings,
arbitrary persistence sectors or dishonest devices. The existing simulator's
16 MiB file bound and prefix/durable-name model apply. Virtual time remains
constant during a single API call, so elapsed-time budgets do not interrupt
that call. This does not qualify checkpoint time slicing or latency. Notification
sockets, preallocation and recycling are
excluded. Real-kernel completion I/O is a separate proof; a process reopen is
not physical power-loss qualification.

Writing this fixture does not establish a passing result. Measured qualification
belongs in the lane report after remote execution.
