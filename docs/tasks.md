# Tasks that come home together

`tasks.together` gives child work a lifetime. Its ordinary callback starts
workers and reads their typed replies. Returning from the callback waits for
every unobserved reply. The scope returns only after every child process has
been closed and reaped, including on a body error, a task error, cancellation
or a timeout. No `async` annotation or special calling convention is needed.

```minyar
use "tasks" as tasks
use "workers" as workers
use "errors" as errors

let greetings = tasks.channel(tasks.text(), tasks.text())
if workers.isWorker() {
    tasks.serve(greetings, function(name: Text): Result<Text, errors.Error> {
        return Ok("Welcome home, " + name + ".")
    }).unwrap()
} else {
    let messages = tasks.together(5000, function(scope: tasks.Scope): Result<List<Text>, errors.Error> {
        let ada = try tasks.start(scope, "greet", greetings, "Ada")
        let grace = try tasks.start(scope, "greet", greetings, "Grace")
        let first = try tasks.response(ada)
        let second = try tasks.response(grace)
        return Ok([first, second])
    }).unwrap()
    for message in messages { print(message) }
}
```

`together` returns the callback's typed value after joining the children and
finishing cleanup. Lists, records and Bytes keep their ordinary ownership and
remain usable after the scope closes. Callbacks returning `Result<Nothing,
errors.Error>` still finish with `Ok()`. Any body error, unobserved task error,
cancellation or deadline failure replaces the callback's successful value;
producing a value does not end the scope early.

Each task re-executes the current program with the existing worker entry
arguments. `workers.mode()` distinguishes different handlers. `tasks.serve`
reads one request, decodes it, calls the handler, encodes its result and sends
one terminal reply. An `Err` from a decoder, handler or encoder becomes a
task failure. A clean EOF without a task reply and malformed replies are
failures too. A reply marks the end of task work: the coordinator may reclaim
the process immediately. Put no work after `serve` returns. These are
one-shot tasks, with no graceful process-exit-status contract.

`Channel<Request, Reply>` carries a codec for each direction. `tasks.bytes()`,
`tasks.text()` and `tasks.integers()` provide codecs for Bytes, valid UTF-8
Text and signed 64-bit little-endian Integers. `tasks.codec(encode, decode)`
provides a codec for a record or another type; both callbacks return Result.
`tasks.channel(requestCodec, replyCodec)` gives those types to `start` and
`serve`. Request and reply types may differ. A mismatched request is a compile
error. A custom decoder validates the received representation before it
constructs a value. Each reply decoder runs once; repeated `response` calls
inside the scope share the cached value.

Managed values and codec closures stay in their creating execution domain.
Workers own separate heaps and receive copied Bytes. There are no shared
managed writes or ownership operations across threads. The request Bytes
can therefore be changed after `start` returns without changing the child's
request. This uses process isolation rather than the disjoint slots of
`parallel for`. The coordinator callback runs sequentially; callbacks
themselves are not submitted to another thread.

The event loop watches every outstanding worker's reading pipe and any
pending request writes. Waiting for one task services its siblings too;
later tasks can complete or fail while an earlier task is still working.
The first observed task or body failure cancels all remaining work. Handling
that error inside the callback does not restore the scope to success.
`tasks.cancel(scope)` cancels every child and is idempotent while the scope
is active; `together` returns an error with `errors.cancelledCode()`.
Scope and Task aliases retained after the callback ends return
`errors.closedCode()` and cannot start or revive a child. Plain reply values
may leave the scope and keep their normal ownership semantics.

The timeout is one absolute monotonic deadline for the whole scope, including
encoding, starting and receiving. It accepts -1 for no deadline or 0 through
2147483647 milliseconds; zero is already due. Nested coordinator scopes
inherit the earlier deadline. Expiry returns `errors.timedOutCode()` and
cancels the children. The coordinator checks the deadline at task operations
and after user callbacks. It cannot preempt arbitrary CPU work or another
blocking library operation inside those callbacks. Codecs must not recursively
wait for or start tasks while replies are being decoded.

This first slice supports hosted macOS and Linux. `tasks.supported()` reports
availability. Windows workers do not yet expose readiness through the socket
event loop, so `together` returns an unavailable error there. A task worker
cannot open another task scope; descendant process trees and streaming
channels are not part of this slice. The lower-level worker and native process
APIs retain their separate, manually managed lifetime contracts.

Each child costs a process, its own heap, two pipes and copied message frames.
Managed scope, task, codec and Result containers also allocate. Request frames
keep the existing 16 MiB limit and 32 MiB pending-send limit. Task replies use
a 24-byte envelope, leaving 16777192 bytes for a successful reply payload.
The event loop performs readiness waits rather than timed polling.

Run the [together gallery](../examples/gallery/together.min) to receive two
letters from separate workers. `make check-structured-tasks` checks the typed
protocol, scope cleanup, cancellation, deadlines and failure paths at O0/O2.
