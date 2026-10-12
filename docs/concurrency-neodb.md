# WS1: applying safe threads to neo-db

Research/design draft, 2026-10-12. Inspected `~/Projects/neo-db` at `3ee206ba073b2a7611bdb63ac219e3af513b0ade`, with no tracked changes to the inspected `src/` and `docs/` files. No neo-db code or gaps were edited. The Minyar model is proposed in [concurrency-design.md](concurrency-design.md); no threaded executor is implemented or benchmarked by this work.

## Decision

Use a bounded set of **executor domains**, each with local mutable evaluation state, and actual shared immutable input/program buffers with atomic cross-thread lifetime. Keep sessions and transactions pinned to one owner. Start by offloading storage jobs and read-only computation; evolve to data-owning shards only with an explicit routing and transaction protocol. A channel stage that moves only Bytes is useful groundwork, but is not completion of WS1's shared managed immutable memory objective.

Do not concurrently call the existing `engine.execute(e, s, ...)` with one shared `Engine`, or protect only its top-level reference count. A global mutex around whole statements would retain one executor at a time; locks around individual fields would lose the current statement/visibility invariants. The source requires a separation of immutable executable/input data from mutable execution state.

## Evidence from the current executor and gaps

Evidence paths below are relative to the neo-db checkout and refer to the revision above; source takes precedence over older architecture prose.

- [`docs/adr/001-single-threaded-event-loop.md`](/Users/luke/Projects/neo-db/docs/adr/001-single-threaded-event-loop.md) selects one event-loop owner because Minyar cannot send managed values through the scalar parallel ABI. [`009-what-the-benchmarks-overruled.md`](/Users/luke/Projects/neo-db/docs/adr/009-what-the-benchmarks-overruled.md) records a multicore need for OLTP/YCSB, loop-thread checkpoint stalls, and a separate analytics/vectorization need. These are neo-db's recorded findings, not new measurements here. More threads do not fix query decorrelation.
- [`src/engine/api.min`](/Users/luke/Projects/neo-db/src/engine/api.min) `Engine` owns catalog, transaction manager, mutable `Env`, plan/view caches, commit list and WAL. `runPlanned` changes `env.me` / `env.nowMicros` and resets reusable plans. `Session` holds transaction state, COPY buffers and savepoints; `Prepared` is not just immutable SQL text.
- [`src/engine/exec.min`](/Users/luke/Projects/neo-db/src/engine/exec.min) `Plan` combines instruction vectors with writable registers (`rNull`, `rInt`, `rBuf`, offsets/lengths), scratch, operator cursors, table slots, hash maps and an `Env` referencing catalog/transactions. `loadCell` stores a table column's byte arena directly in `rBuf`. A cached plan or read-only query can therefore alias mutable table storage and mutate its own cached execution state.
- [`src/engine/table.min`](/Users/luke/Projects/neo-db/src/engine/table.min) columns contain mutable data, text heaps, null bitmaps and scales; tables contain mutable row state, index references and counters. Ordinary Bytes/records retain alias semantics. An atomic count on `Table` does not freeze these descendants.
- [`src/engine/txn.min`](/Users/luke/Projects/neo-db/src/engine/txn.min) `TxnMgr.locks`, `waitsFor`, `serialOwner` and `lockEpoch` implement SQL lock/visibility state **on one owner thread**. These are not native mutexes. `visibility` / `loadBeforeImage` read another transaction's undo buffer. `finishCommit` releases locks and resets that buffer after durability.
- [`src/server/server.min`](/Users/luke/Projects/neo-db/src/server/server.min) keeps `Conn`, portals and socket state local; `Server.out`, `rbuf`, empty values and startup caches are loop-wide scratch. Workers must not borrow these while the loop reuses them. Held replies wait for `holdLsn`; stale connection tokens must not authorize a late completion.
- [`docs/MINYAR_GAPS.md`](/Users/luke/Projects/neo-db/docs/MINYAR_GAPS.md) G1/G3 already record the durable-files fork and fsync syncer; [`lib/dbio.min`](/Users/luke/Projects/neo-db/lib/dbio.min) now wraps Minyar `files`/`system`. Older `ARCHITECTURE.md` and ADR-004 still describe `native/dbio.c`. General managed background jobs remain an additional capability; do not mark G3 newly fixed for a design. G13 concerns local cleanup/borrow costs and belongs to WS2; global atomic RC would worsen its hot path. G14–G16 concern process-fatal faults: threads alone do not isolate bad SQL.

## Proposed ownership boundaries

| State/resource | Exclusive owner | Crossing mechanism / synchronization |
| --- | --- | --- |
| Connections, sockets, input/output scratch, protocol portal names/ids and reply ordering | Connection's event-loop domain | Scalar request/connection generation ids plus detached request/reply buffers; no `Conn` pointer |
| Session, transaction/savepoints/COPY state and executing portal/cursor state | One pinned executor/data owner | Commands/results through bounded channels; disconnect requests cooperative abort on that owner |
| Registers, cursors, `Env`, errors, scratch, temporary tables/maps | One execution instance in one executor domain | Never share `ex.Plan`; instantiate mutable state separately |
| Immutable instruction/schema bytes and consistent read-only batches | SharedFrozen native backing, accessed via local FrozenBytes handles | Atomic strong lifetime + queue publication; versioned immutable contents, no writable Bytes view |
| Mutable table columns, indexes, undo, row-lock map | One data shard (initially the existing engine owner) | Route work to owner; take consistent copies/frozen versions before offloading reads |
| WAL append order, LSN assignment, durability progress, file rotation | One WAL owner initially | Ordered redo requests and durable acknowledgements; retain native fsync synchronization |
| Snapshot output, compression/checksum work | Storage job's OS thread; capture/version belongs to data owner | Detached encoded chunks or shared immutable versions, bounded credits; no live catalog/table pointers |

Native locks guard **channel/control state**, not ordinary local Minyar graphs. A thread-safe endpoint creates a receiver-local managed shell. Runtime native registries must be synchronized or kept under one coordinating owner; per-job locks do not make an unsynchronized registry safe.

## Stage A: background jobs and executor instances

Leave engine/catalog/transaction ownership on the existing loop while establishing safe thread startup, local collectors and channels. Encode a request into independent storage before handoff. Transfer detaches only that request Bytes shell and empties its sender aliases; do not detach `Server.rbuf`, `Plan.rBuf`, `Txn.redo` or `Wal.buf` while their owners still depend on their contents. Build a separate job buffer, or rotate the owner's buffer into a prepared empty replacement at an explicitly safe boundary.

A storage worker receives a local Bytes shell, owns file descriptors or duplicates for its job, and returns a scalar status plus a detached completion buffer. It may kernel-block in pwrite/fsync/compression; the network loop uses readiness and try-send/try-receive. Close/reuse of the original fd must not change the worker's target. Preserve WAL coverage ordering during rotation; the current `files` syncer already duplicates its fd and is a useful pattern, not a generic managed thread API.

For executor sharding, split current `ex.Plan` conceptually into immutable **program** and per-execution **state**. First encode the instruction vectors, type ids, literals and schema version into one FrozenBytes program; each executor retains the same immutable allocation and owns independent registers/scratch/cursors. A bounded snapshot batch similarly freezes column data, text arena, null/scales and row visibility for a defined statement version. Native/Minyar readers must accept FrozenBytes directly or copy explicitly; casting it to mutable Bytes defeats isolation. A text span must retain its frozen owner alongside offset/length until its last consumer finishes.

Read-only jobs use `(request id, schema version, read version, frozen program, frozen input)` and return independently owned rows/partial aggregates. Their `Env` cannot name the live `Catalog`/`TxnMgr`; resolve catalog ids and visibility on the owning domain when capturing the batch. Current before-image visibility cannot be read remotely while the owning transaction resets its undo. Re-plan/retry mismatched schema versions under an explicit policy. Reads with volatile functions/time/random/side effects need defined statement context or stay on the owner. Sharing already compiled `Prepared`/`Plan` records is not this stage.

Actual shared immutable buffers become essential for scans used by multiple executor domains: the same input backing is retained concurrently without repeated large copies. Publishing a buffer is safe only after its content/version are fixed; a snapshot copy has a cost even when its later fan-out is zero-copy. Local RC, local Text headers and per-thread collectors stay on each executor.

## Stage B: data-owning executor shards

Choose a stable partition key and pin sessions/transactions to their data owner. Each shard owns its catalog instance, table/index partitions, `TxnMgr`, plan cache, `Env`, counters and mutable heaps. Keep active transactions/COPY/portals on that shard; migrate only at a proven quiescent boundary. DDL/schema changes require ordered coordination and versioned immutable publication, not mutation of a shared catalog.

The current Portal record mixes wire-protocol metadata with Prepared, row and execution references. Stage A keeps both on the existing owner. Stage B splits them: the connection loop owns protocol names, request sequencing and opaque generation ids, while the executor owns Prepared values, execution cursors, row buffers and COPY state. Bind/execute/close/cancel commands exchange ids and independently owned buffers; no portal or Prepared pointer crosses domains. Pin execution state for the portal's lifetime and reject stale-generation commands or completions.

One independent `engine.open` per thread over **the same data directory** is unsafe: it would produce competing WAL/checkpoint owners. Independent Engines are valid only for deliberately separate stores, or after a new storage/coordinator interface defines ownership. Routing clients to independent database copies is not sharding one consistent database.

For initial sharded writes, keep a single WAL coordinator: shard sends `(shard id, txn id, generation, owned redo)`; coordinator assigns an ordered global LSN, writes and requests fsync, then publishes durable progress/completion. The shard alone transitions its `Txn` and releases SQL row locks; its connection owner alone releases held replies. The original `commitTxn`, `releaseDurable`, `Wal.requestSync` and `Server.holdLsn` order must survive. Durability notifications can be scalar/channel messages; an atomic progress counter alone does not transfer transaction state or guarantee that its redo was included.

Cross-shard statements, global unique indexes/foreign keys, joins and transactions require a deliberate protocol. Until one exists, route the entire operation to one owner when its data is local, or reject the unsupported partition span. Do not silently split a transaction into separately durable commits. Multi-shard atomic commit requires durable prepare/decision/recovery semantics; a broad “use channels” claim is insufficient. SERIALIZABLE's current single `serialOwner` must remain global through a coordinator token or be replaced by a proved distributed policy. READ COMMITTED snapshots and deadlock/wait ids need shard and generation identities. A local `lockEpoch` is not a global release epoch.

## Checkpoint and shared snapshot constraint

[`src/engine/api.min`](/Users/luke/Projects/neo-db/src/engine/api.min) `checkpointBlocked` / `checkpoint` construct a consistent snapshot while engine work is serialized, including special handling for spilled transaction records and before-images. [`src/storage/snapshot.min`](/Users/luke/Projects/neo-db/src/storage/snapshot.min) `finishWal` requires covering WAL durability before publishing the snapshot, followed by temp-file sync, rename and directory sync. Preserve those constraints.

Moving the write/fsync/CRC work off-loop is achievable with already encoded independent chunks. Moving **capture/encoding** off-loop while writers mutate current column Bytes is unsafe. To eliminate that pause later, use immutable versioned blocks/copy-on-write under the data owner, or a defined capture barrier that retains a consistent version while workers read it. Encoding batches over successive loop ticks without versioning does not produce one consistent LSN snapshot. Bound pinned old-version bytes and queued capacity; if the writer falls behind, apply backpressure rather than accumulating another full database snapshot.

With shared immutable blocks, executor readers and checkpoint writers can retain the same backing concurrently using FrozenBytes atomic ownership. A returned span/block still owns its backing; releasing a source table/version does not invalidate it. Global consistent checkpoints across data shards need a coordinated capture cut plus covering WAL position; a collection of unrelated shard-local LSNs is insufficient.

## Locks, channels and failure policy

Use short native mutex/condition critical sections for queue capacity/close and thread-control lifetime. Bound both message count and **retained allocation capacity**, including zero-length messages with spare storage. The event loop never blocks sending into a full queue; disable/limit incoming work and resume when credits return. Native readiness notification follows publication and uses a drain/recheck protocol to avoid lost wakes. No channel mutex spans SQL execution, user callbacks, fsync or collector work.

Database row locks remain logical locks owned by the data domain, held until its covering durability acknowledgement. Applications must not hold a native shared-memory mutex while waiting for those acknowledgements. Define a deterministic coordinator ordering for multi-owner operations, and keep channel calls outside any future guarded-data critical section. Shared mutable lock wrappers are outside the initial byte-sharing API; references must not escape their guard if later introduced.

Each request/completion includes connection generation, session/shard identity and request sequence. A disconnected/reused connection drops stale replies safely; transaction cleanup stays with its owner. Cancellation is cooperative and cannot undo an already durable commit. Shutdown stops admission, drains or cancels queued work with defined ownership, completes WAL obligations, releases pinned versions, closes channels and joins threads. A stopped/failed thread wakes waiters; native control shares outlive its local heap. Existing process-fatal Minyar traps remain a whole-database fault boundary.

## Reviewer decisions and qualification dependencies

1. Accept FrozenBytes as the first **actual shared managed immutable representation**, while keeping all mutable executor/data graphs shard local. Require simultaneous-reader and creator-exit lifetime evidence, not just channel copies.
2. Pick the first consumer: bounded checkpoint write/checksum jobs offer a smaller integration than parallel execution over live tables; neither proves off-loop snapshot capture. Benchmark CPU-bound parsing/execution independently from I/O waits.
3. Define partition ownership, transaction routing and a single WAL coordinator before parallel writes; explicitly defer unsupported cross-shard transactions and schema operations.
4. Preserve G13 and the ≤1% unchanged single-thread performance gate; benchmark end-to-end throughput, tail latency and pinned/queued memory when the hold lifts. Re-run durability/crash/visibility suites for any later database implementation.

The parent owns [the qualification plan](research/concurrency-qualification.md) once these drafts are copied into Minyar `docs/`. This research closes no gaps and requests no implementation, builds, Boat work or spending while the integrator hold remains.
