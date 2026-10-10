# Hosted readiness loop and timers

`use "eventloop" as loop` provides socket readiness and monotonic timers in
owned batches. macOS/BSD use kqueue, Linux uses epoll, and Windows uses WSAPoll.
It is a single-owner API: ordinary Minyar values and registrations are not
safe to share between threads. It does not implement language closures or
async/await. Native socket operations use recoverable values from `errors`.

`net.read` separates stream EOF, would-block and failure. `net.write` returns
the number of bytes written in one operation; callers retain any unsent suffix.
`net.receiveDatagram` distinguishes zero-length packets from would-block and
marks truncated packets explicitly. `net.sendDatagrams` sends a connected
UDP batch of at most 64 packets. `net.receiveDatagrams` preserves each packet's
boundaries, numeric source address, port and truncation status. Linux uses
`sendmmsg` and `recvmmsg`; other hosts use nonblocking socket calls. Every batch
is bounded, and the entire send encoding is checked before transmitting its
first packet. `net.sendDatagramTo(socket, source, port, data)` replies to a
numeric IPv4/IPv6 peer without connecting the UDP socket or performing DNS.
It returns an owned `IntegerResult`, preserves empty datagrams and validates
the complete address/packet before I/O. UDP GSO/GRO and unconnected batch send
are not implemented yet. `net.monotonicMilliseconds()` supports absolute
operation deadlines across multiple reads.

```minyar
use "eventloop" as loop
use "errors" as errors
use "net" as net

let handle = errors.integerValue(loop.create())
let socket = net.udp("127.0.0.1", 0)
let watch = errors.integerValue(loop.watch(handle, socket, loop.readableInterest(), 42))
let heartbeat = errors.integerValue(loop.timer(handle, 15000, 15000, 99))
let batch = loop.wait(handle, 1000, 128)
if errors.isError(loop.batchError(batch)) {
    print(errors.message(loop.batchError(batch)))
} else {
    for event in loop.events(batch) {
        if loop.isTimer(event) { print("heartbeat") }
        if loop.isReadable(event) {
            let packet = net.receiveDatagram(socket, 65535)
            if errors.bytesStatus(packet) == errors.successStatus() {
                print(errors.bytesValue(packet).length)
            }
        }
    }
}
loop.remove(handle, watch)
loop.remove(handle, heartbeat)
loop.close(handle)
net.close(socket)
```

The example explicitly asserts successful setup with checked scalar extractors.
Applications can inspect each setup/removal result and recover instead. Check
read status before treating a truncated datagram as a complete packet. Empty
UDP datagrams are successful data; TCP EOF is a separate outcome.

## Contract

- `create()` returns `errors.IntegerResult`. The loop handle contains a slot
  and generation; closing/reopening does not resurrect an old handle.
- `watch(loop, socket, interest, token)` returns a registration handle and
  enables nonblocking mode. Interest is 1 (read), 2 (write), 3 (both), or 0
  (pause ordinary read/write events). Duplicate watches fail recoverably.
- `update(loop, registration, interest, token)` changes socket interest/token.
  `remove(loop, registration)` removes a watch or cancels a timer. Both return
  `errors.BooleanResult`. Unknown, cross-loop and expired registrations fail.
- `timer(loop, delayMs, periodMs, token)` returns a registration handle.
  Nonnegative delay zero fires on the next wait. Period zero is one-shot;
  positive periods repeat from the current monotonic time, skipping missed
  intervals. A repeating timer fires at most once in a returned batch.
- `wait(loop, timeoutMs, maxEvents)` returns a `Batch`, with `events(batch)` and
  `batchError(batch)`. Timeout is -1 (indefinite) or 0 through INT32_MAX ms.
  Maximum batch size is 1 through 65,536. A successful timeout is an empty
  batch, distinct from failure. Signals do not restart the absolute deadline.
- `close(loop)` releases selector, registry and timer storage. It leaves the
  application's sockets open. Remove a watch before closing/reusing its socket.
  A one-shot timer registration expires when its event is emitted.

Each Event contains `registration`, the caller's signed Integer `token`,
`flags`, `nativeCode` and `kind`. Flags are read=1, write=2, close=4, error=8,
timer=16; helpers test them. Kind 0 is socket, kind 1 is timer. Close/error
flags are hints and may differ across OSs; the actual read/write result is
authoritative. Event native codes can be zero when the selector only supplies
an error hint. Do not infer success from a readiness event. Writable interest
should be enabled only when data awaits transmission, since a writable socket
can otherwise keep a level-triggered loop awake.

Native envelopes are little endian. Scalar operations return 16 bytes:
`u32 status, u32 nativeCode, i64 value`. Wait returns an eight-byte status/code
header followed by fixed 32-byte events: `i64 registration, i64 token,
u32 flags, u32 nativeCode, u32 kind, u32 reserved`. The wrapper validates shape
and returns owned records. No mutable last-error state is used to construct an
operation result. Constructing envelopes, Lists and Event records has a real
allocation cost; this is not an allocation-free callback or zero-copy API.

## Scaling and timer work

POSIX waits ask the kernel for ready registrations, without scanning the full
registry. Watch lookup uses a socket hash table; generation validation is
constant-time. WSAPoll needs a socket array and scanning; Windows currently
does this linear work and rotates the starting position to avoid repeatedly
returning the same small prefix. IOCP is a future implementation, not a claimed
property of this backend.

Timers use an indexed min-heap. Insert/cancel costs O(log n); cancellation
removes the heap entry immediately, so repeated long-delay cancellation cannot
accumulate tombstones. Reusable slot arrays retain high-water capacity until
loop close. Positive-generation IDs never wrap; exhaustion returns a failure.
Timers and sockets share bounded batches, reserving capacity for due timers.
For a batch of one, preference alternates. Timer deadlines break ties by
registration order. A failed selector wait does not consume due one-shot
timers. Repeating timers do not emit a catch-up storm after a slow application.

An idle loop blocks until its deadline, the earliest timer, or kernel readiness.
There is no polling sleep loop. This does not establish hours-long idle CPU or
memory behavior: the checked native test measures a 100 ms blocked interval
and verifies process CPU consumption below 50 ms, plus timer/registration
storage reuse. Production measurements and sustained soaks remain separate.

## TDD, peer sources and measured verification

`tests/net-loop.c`, `tests/net-loop.py` and `tests/net-loop.min` were added before
the backend; the initial compilation failed on absent native loop functions.
Tests then exposed and drove two fixes: preserve due timers across selector
failure, and enable nonblocking when watching a previously blocking socket.

The executable C suite exercises 2,048 real loopback UDP sockets with 31-event
batches alongside 100 due timers, ordered/repeating/zero-delay timers, token
and interest changes, duplicate watches, stale/cross-loop/reopened handles,
one-shot expiration, invalid argument ranges, 20,000 long-delay timer
cancellations with exact bounded registry/heap assertions, loop/socket ownership
and interrupted wait deadlines. The signal test repeatedly interrupts a wait
without extending its 100 ms deadline. The Minyar fixture verifies typed
envelopes/ownership and recoverable failures at `--debug` and `--release`.

Recorded on macOS arm64: native O2 and ASan/UBSan C suites passed, including
2,048 sockets, and compiled Minyar debug/release passed. The 100 ms idle wait
used approximately 0.0003–0.0004 process CPU seconds in those runs. Linux epoll
native O2 and ASan/UBSan with LeakSanitizer enabled passed in the existing local
LLVM 23 Docker image (no paid infrastructure). Its idle samples were about
102 ms and 0.0005–0.0006 CPU seconds. The complete native network translation
unit also passes MinGW Windows cross-compilation with `-Wall -Wextra -Werror`.
Windows backend execution and Linux Minyar module execution must be established
by their platform gates; cross-compilation and macOS results do not establish
either. These samples are test evidence, not throughput claims.

The sources below were inspected and scenarios independently written; no
upstream code or harness was copied. Source hashes identify the sampled file.
Semantics deliberately differ: Minyar exposes level-triggered batches rather
than Mio's portable edge-oriented obligations or libuv callback lifecycles.

| Source | Pinned revision / source SHA-256 | Adaptation |
| --- | --- | --- |
| [Mio poll tests](https://github.com/tokio-rs/mio/blob/a88e5e119172e4fb1638926faf65a4fe889e05b1/tests/poll.rs) | `a88e5e119172e4fb1638926faf65a4fe889e05b1`; `48bc04ef549991784ab059d58810f498e332118952ac3f7bf19551008ca6129d` | Zero timeout, changing interest/token, deregistration and erroneous registration; ordinary managed Minyar references do not inherit Mio's Send/Sync guarantee. |
| [Mio UDP tests](https://github.com/tokio-rs/mio/blob/a88e5e119172e4fb1638926faf65a4fe889e05b1/tests/udp_socket.rs) | Same revision; `2a52c5f88544d424ed768d95584151f4a05e68f4e500cfd7f5ad4077193a7a72` | Real datagrams/readiness, re-registration and no events after removal, preserving empty packet semantics. |
| [libuv timer tests](https://github.com/libuv/libuv/blob/84318be9a4568f1ea3c897c0db0d3504d2b8ebde/test/test-timer.c) | `84318be9a4568f1ea3c897c0db0d3504d2b8ebde`; `66020ed00e81e1d6edb479e0b529c67370b13f0a342344169d90d43e8c95a0f1` | Ordered timers, zero timeout, single/repeat lifecycle and avoiding double delivery. |

Design references: [libuv's single-thread loop](https://docs.libuv.org/en/v1.x/design.html)
and [timer semantics](https://docs.libuv.org/en/v1.x/timer.html),
[Mio's readiness caveats](https://docs.rs/mio/latest/mio/struct.Poll.html),
[Apple's kevent reference](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/kevent.2.html)
and [Microsoft's WSAPoll reference](https://learn.microsoft.com/en-us/windows/win32/api/winsock2/nf-winsock2-wsapoll).
Mio and libuv repository licenses are MIT/Apache-2.0 and MIT respectively;
copying actual files would require their applicable notices and provenance.

Remaining work includes callbacks/closures and ownership-domain enforcement,
macOS AppKit/CFRunLoop integration with a wake source, IOCP, cancellable
cross-thread wakeups, io_uring evaluation, millions-of-connection memory/idle
benchmarks and hours-long mixed socket/protocol soaks. Socket batching belongs
to the `net` module. The basic reactor does not implement QUIC, Linux GSO/GRO,
connection migration or transparent TCP fallback.
