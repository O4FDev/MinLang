# Completion I/O

`completionio` provides a bounded Linux `io_uring` queue for positioned
regular-file reads, copied writes, and ordered file syncs. Recoverable failures
use `Result`; an empty completion stream uses `Maybe`. The native handle and
raw status interface are private.

`create(capacity, maximumBytes)` returns `Result<Queue, errors.Error>`.
A successful creation means the restricted ring was enabled; it does not promise
that a particular filesystem's I/O will succeed. This slice needs Linux 5.10 or
later and permission to use io_uring. Other systems or builds without suitable
Linux headers return an error whose positive native code is ENOTSUP. Linux setup,
mapping and restriction failures preserve codes such as EPERM, ENOSYS and EINVAL.
There is no synchronous-I/O fallback.

Capacity is 1–1024 outstanding operations, including staged operations and
completed ones whose results have not been collected. The aggregate C buffer
budget is 0–67,108,864 bytes per queue, including each requested read/write size
until collection. A full queue or exhausted budget returns an error with native
code EAGAIN; it does not wait or grow. At most 64 queues may be live per thread.

The public operations are:

```minyar
create(capacity, maximumBytes): Result<Queue, errors.Error>
queue.read(file, offset, length, token): Result<Integer, errors.Error>
queue.write(file, offset, bytes, token): Result<Integer, errors.Error>
queue.sync(file, token): Result<Integer, errors.Error>
queue.submit(): Result<Integer, errors.Error>
queue.staged(): Result<Integer, errors.Error>
queue.pending(): Result<Integer, errors.Error>
queue.next(wait): Result<Maybe<Completion>, errors.Error>
queue.close(): Result<Nothing, errors.Error>
completion.count(): Result<Integer, errors.Error>
completion.bytes(): Result<Bytes, errors.Error>
```

The read, write and sync methods stage an operation and return its positive ID,
unique within that queue. The signed token is returned unchanged. Each staged
operation holds a close-on-exec duplicate of the supplied descriptor and its own
C buffer when needed. Closing the original descriptor is safe. Only regular
files are accepted; sockets, pipes, directories and devices produce ENOTSUP.
Direct I/O reads/writes and append-mode writes also produce ENOTSUP. Offsets and
lengths must be nonnegative and their sum must fit Integer.

The queue belongs to its opening thread. Calling its methods from another thread
returns an error with native code EBADF. Close it on its owning thread before
that thread exits. Do not use queues across `fork`, change shared
file-description flags while operations are pending, or externally close the
private duplicate descriptors. Queue aliases share the same native resource;
closing one invalidates all of them. The private handle prevents callers from
forging or replacing a queue's identity.

No background thread or kernel operation receives managed `Bytes`. A write
copies its payload before returning. A read uses a C buffer; `next` copies the
completed bytes into managed storage on the caller. A collected read's bytes
remain valid after the queue closes.

`submit()` makes one `io_uring_enter` call without requesting a completion
wait. Its result is the number submitted. Partial submission and an interrupted
call preserve all owners. Inspect `staged()` and retry the remaining entries;
do not enqueue the same logical operation again after an interruption. Errors
carry a positive OS code through `failure.nativeCode()`, so Linux EINTR is 4.
Shared unsigned 32-bit heads and tails handle wraparound. SQ publication and CQ
consumption use release stores; kernel-written heads and tails use acquire loads.
The queue never exceeds either the outstanding-operation bound or CQ capacity.

`next(false)` does not request a completion wait. It may enter the kernel with
a zero minimum completion count to run task work. `next(true)` explicitly waits
for a submitted operation. Both return `Ok(None)` for an empty queue. When every
operation is staged, a waiting call returns EAGAIN instead of hanging. Collection
does not submit. Interrupted collection returns an error with native code EINTR.

Neither submission nor non-waiting collection guarantees bounded latency: either
can spend time executing kernel or filesystem work.

`Ok(Some(completion))` means an operation was collected. Its public `id`,
`token` and `kind` identify it; kind is READ, WRITE or SYNC. An operation that
failed in the kernel still arrives this way, preserving its identity.
`completion.count()` reports the operation's error or its byte count, including
short reads/writes, zero at EOF, and zero for a successful sync.
`completion.bytes()` returns copied bytes only for a successful READ. An
operation failure remains an error; asking a successful WRITE or SYNC for bytes
returns a recoverable invalid-data error. The raw result and buffer fields are
private. Completions may arrive out of order.

Native failures use `errors.systemCode()` and the positive OS code, with an
operation context. Asking the wrong completion kind for bytes uses
`errors.invalidDataCode()` and native code zero. Errors returned by `next`
itself describe collection failure, separate from a particular completion's
operation failure.

`sync(file, token)` uses FSYNC with IOSQE_IO_DRAIN. The ring starts disabled,
allows only READ, WRITE and FSYNC, explicitly permits the IO_DRAIN SQE flag, then
enables the restrictions. All earlier operations on every file finish before the
sync starts, including short or failed operations. The sync makes only its
supplied file durable; it does not sync other files merely because their
operations finished. Check every write's exact count and the sync's zero count
before acknowledging that file's batch. A successful sync cannot turn an earlier
write failure into success. Do dependent reads after observing their writes.
Operations after a barrier are outside its durability promise. New names and
renames also need directory sync, through `files.flushDirectory`.

`pending()` includes every operation not yet collected, even if the kernel has
finished. `close()` returns EBUSY while any operation remains, including staged
and completed but uncollected operations. A failed busy close leaves the queue
usable. Submit staged operations, collect all completions and handle their
results, then close explicitly. Stale aliases and double close return EBADF.

Dropping a Queue or a Result does not close its native resource. There is no
implicit finalizer, cancellation or force-close in this slice. Applications must
arrange cleanup when returning an error. A permanent submission failure may leave
owners that cannot safely be freed until process termination. Lost or malformed
ring events return EOVERFLOW or EIO while retaining those owners.

Costs are explicit: a copied write buffer or reserved read buffer and one
duplicated fd per outstanding operation, a bounded owner table, kernel SQ/CQ and
SQE mappings rounded to kernel ring sizes, and a linear search of at most
capacity owners for each completion. Every native collection attempt allocates a
managed result packet, including empty/error outcomes. The typed layer constructs
Queue, Result, Maybe and Completion values; successful collection also copies
the packet's data slice. Errors construct Error/context values. These managed
values and copies are outside the C buffer budget, as are kernel worker and
filesystem memory. There are no pinned managed buffers or per-operation
userspace threads.

See [durable-batch.min](../examples/gallery/durable-batch.min) for an example
that checks both typed write counts, the sync, and the new filename's sync. The
example treats unexpected failures as fatal. A service should match those errors
and implement its own drain/close policy before propagating them.

Checks remain separate:

- `make check-completionio-native`: mocked syscall/mapping controls and forced
  unsupported raw ABI. Includes partial submission, EINTR with consumed work,
  u32 wraparound, CQ errors, short results, ordering identities, stale handles,
  copied data/fd lifetime, capacity/budget limits and mapping cleanup.
- `make check-completionio`: those controls plus O0/O2 typed Minyar ABI,
  ownership, private-field rejection and gallery fixtures using the explicitly
  mocked boundary on Linux. This is not kernel proof. Other hosts exercise the
  unsupported factory and privacy checks.
- `make check-completionio-kernel`: strict real Linux io_uring
  read/write/drain sync and O0/O2 typed ABI/gallery. Missing or forbidden io_uring
  exits 77 and fails the target; unsupported never counts as kernel proof. The C
  probe has a 30-second hang guard. No mock is linked into this target.
- `make check-completionio-sanitize`: ASan/UBSan/LSan host controls and
  managed ownership fixtures, using the repository's sanitizer configuration.

The [neo-db integration](completion-io-neodb.md) uses these typed queues with
unmodified production WAL and snapshot code in a separate strict kernel proof.

Primary references: [io_uring overview](https://github.com/axboe/liburing/blob/master/man/io_uring.7),
[setup](https://github.com/axboe/liburing/blob/master/man/io_uring_setup.2),
[restrictions and registration](https://github.com/axboe/liburing/blob/master/man/io_uring_register.2),
and [submission and completion errors](https://github.com/axboe/liburing/blob/master/man/io_uring_enter.2).
