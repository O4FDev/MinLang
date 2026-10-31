# Lane `gaps`: register of Minyar gaps other projects hit (2026-10-30)

Minyar under test: v2 tip **3832f4373** (worktree `~/Projects/minyar-goal-20261030/wt/gaps`, compiler built on the
laptop, macOS arm64; Linux re-tests on box B). Every repro lives in `~/Projects/minyar-goal-20261030/reports/gaps-repros/`
(`R/` below) and is compiled with `R/run.sh FILE.min [flags]` = `./minyar --release R/FILE.min -o R/bin/FILE`, then run.
No Minyar or product code was changed by this lane. Raw sweep notes: `reports/gaps-work/repos.md` (product repos) and
`reports/gaps-work/runs.md` (run notes 10-18, 10-20, 10-25); every row below that cites them was re-checked here
unless the row says "not re-tested".

STATUS: complete for this pass (02:30). Counts and build order in "Summary" at the end.

## Log
- 01:05 compiler built in the worktree (40 s). neo-db `minyar-gaps/*.min` copied to `R/` and re-run.
- 01:20 parallelism probes P1-P6 written and run.
- 01:35 **finding: real threads exist but are undocumented.** `thread function` + `startThread/joinThread`,
  `bytesChannel`, `freezeBytes`, `NativeRegion` atomics (compiler/thread-compiler.min, tests/thread-fixtures/,
  build-support/thread-*.mk; first landed 2026-10-12). `grep -rn 'thread function' docs/` finds nothing. neo-vm uses
  them for vCPUs (neo-vm vmm/kvm.min:154). Probes T1-T8 below.
- 01:45 **finding: a program that starts a `thread function` cannot use `net`, `files`, `eventloop`, `io.readTextFile`
  or even `system.processId` anywhere, including on the main thread** (`R/t6_*`, `R/t8_*`: "unsafe thread effect in
  'listen': native 'minyar_net_listen'"). So no server can use the thread feature.
- 02:00 helper sweeps finished; rows merged and re-tested below. `~/Projects/goal-loops/REQUESTS.md` has no rows (header
  only). T3 threads read: "Minyar: real threads" (mcp:cd682ca1, 2026-10-13: threads landed, 8-core scaling 7.075x missed
  its 7.2x gate), "Minyar WS1: shared-memory threads", "Language Perf, DB Roadmap" (SIMD: "Minyar has no explicit
  SIMD types").

## Required parallelism rows

### PAR-1 threads
- **Has (documented):** `parallel for` (docs/language.md "Parallel ranges", docs/parallel.md): persistent pthread pool on
  macOS/Linux, `MINYAR_PARALLEL_THREADS` 1-64, `system.parallelWorkers()` (library/system.min:11); bodies write only
  their own slot/window of an existing scalar buffer and call only `parallel function`s. Process workers: `workers`
  (library/workers.min) and `tasks.together` (library/tasks.min, docs/tasks.md) re-execute the program per task.
- **Has (undocumented):** `thread function f(seed: Integer, input: FrozenBytes | NativeRegion(s), channel: BytesChannel |
  FrozenBytesChannel): Integer | Nothing`; `startThread/joinThread`, `startThreadResult/joinThreadResult`; each thread
  owns a private managed heap (Map/Text/List allowed inside); values cross only as moved Bytes through a channel or
  as immutable `FrozenBytes`. Implemented in compiler/thread-compiler.min + runtime/minyar_threads.h,
  minyar_thread_buffers.h, minyar_thread_domain.h; checks `check-thread-*` (build-support/thread-*.mk). Not in docs/.
- **Probes:** `R/p1_threads.min` -> `workers 10 total 224000000`. `R/p1b_thread_closure.min` (parallel body calls an
  ordinary function that appends to a List) -> `error: parallel for: shared values may only be scalar buffers read by
  index or through .length; managed values cannot escape or be changed`. `R/t1_thread_transfer.min` (copy of
  tests/thread-fixtures/transfer-local.min) -> `managed local transfer passed`. `R/t7_thread_managed.min` (thread
  builds a Map) -> `1`. `R/t2_thread_shape.min` (thread taking a record) -> `error: thread entry 'work' requires
  (Integer, FrozenBytes or native region capability, BytesChannel or FrozenBytesChannel) and Integer or Nothing result`.
  `R/t6_thread_plus_net_main.min` (main thread uses `net.listen`, worker only builds a Map) -> `error: unsafe thread
  effect in 'listen': native 'minyar_net_listen' 1(2,1,1)`; same for `files.open`, `eventloop.create`,
  `io.readTextFile`, `system.processId` (`R/t8_thread_with_{files,eventloop,io,system}.min`).
- **Missing:** (1) documentation of the thread feature in docs/language.md; (2) the whole-program effect ban: a thread
  program must be able to use net/files/eventloop/io/system on threads that own those handles (at minimum on main);
  (3) entry signatures beyond the fixed triple: several channels per thread (in + out), records/Lists/Text arguments
  moved or deep-copied in, closures; (4) shared read-mostly managed data (an `Arc`/frozen record graph, not only
  FrozenBytes) so a DB index or a routing table can be read by every thread; (5) thread-local/global state rules,
  thread names, sleep/park. The runtime's ownership tracking is per domain, so (4) is the design item.

### PAR-2 work-stealing pool
- **Has:** the `parallel for` pool steals chunks of up to 128 indices of ONE flat range; the caller works and joins
  (docs/language.md "Parallel ranges"); windows and per-iteration scratch (f094962b1, 5c51fa258). Freestanding builds
  can install their own scheduler (`machine.setParallelScheduler`, library/machine.min:107).
- **Probe:** `R/p2_fork_join.min` (recursive split whose `parallel for` body recurses) -> `error: parallel for: 'sum'
  must be a pure parallel function; shared state, raw machine operations and native effects could race`; a parallel
  function cannot own a List (`parallel function 'sum' may use only Integer, Float, Boolean and Character values`).
  `R/t3_thread_pool.min` (4 `thread function` workers draining one shared BytesChannel) -> `4999950000` (correct), so a
  hand-rolled pool over Bytes messages is possible, but not over typed tasks.
- **Missing:** a general task pool: submit closures/typed tasks, nested fork-join (`join(a, b)`), recursion, futures
  with results, cancellation; ordinary (non-`parallel`) callees, record methods, record field writes and Text inside
  parallel bodies (R25 reports/parranges.md:55-60); a pool shared by server code.

### PAR-3 atomics (orderings, CAS, fences)
- **Has:** `machine.atomicAdd(address, value)` and `machine.fence()` (library/machine.min:57,101), usable only in
  `parallel function`s reached via `parallelEntry` + `machine.callEntry` (raw Integers). Undocumented, Linux-only:
  `NativeRegion` methods `atomicAddInt64`, `compareExchangeUInt32`, `loadAcquire{UInt8,UInt32,Int64}`,
  `storeRelease{UInt8,UInt32,Int64}` on mmap'd regions shared with `shareNativeRegions` (compiler/thread-compiler.min).
- **Probes:** `R/p3_atomics.min` (safe `parallel for` body calling a parallel function that does `atomicAdd`) ->
  `error: parallel for: 'atomicAdd' must be a pure parallel function; ...`. `R/p3c_atomics_entry.min` (parallelEntry +
  callEntry 4x1000) -> `4000`, but hosted `callEntry` runs on the calling thread. `R/p3b_cas.min` -> `error: module
  'machine' has no function named 'compareAndSwap'`. `R/t4_native_regions.min` (copy of the thread fixture) on macOS ->
  `Minyar stopped: mapping Result` (Linux mmap flags); on Linux box B -> `native-regions passed` (two threads x 10000
  `atomicAddInt64`, CAS, acquire/release all correct).
- **Missing:** typed atomic cells in ordinary memory (`Atomic<Integer>` field/global usable from threads and parallel
  bodies), 64-bit CAS (only UInt32 today), weak CAS, exchange, fetch-sub/and/or/xor/min/max, relaxed/acq_rel/seq_cst
  orderings chosen per operation, acquire/release fences, futex-style wait/notify, and macOS support.

### PAR-4 channels (bounded/unbounded, MPMC, select)
- **Has:** undocumented `bytesChannel(maxBytes, maxMessages)` and `frozenBytesChannel`: bounded MPMC queues
  (runtime/minyar_thread_buffers.h:220-315: mutex+condvar ring, byte and message caps), `sendBytes/trySendBytes`,
  `receiveBytes/tryReceiveBytes`, `closeBytesChannel`; a send moves the Bytes (sender aliases become empty).
  Documented: `tasks.channel(requestCodec, replyCodec)` (one request -> one reply to a worker **process**) and
  `workers.send/receive` (framed messages to long-lived worker processes).
- **Probes:** `R/t3_thread_pool.min` -> `4999950000` (MPMC fan-out works). `R/p4_channels.min` -> `sum 140 in 3072 us for
  8 one-shot tasks` (~0.4 ms per process round trip).
- **Missing:** typed channels (records/Text/Lists moved, not Bytes), unbounded mode, `select` over several channels +
  timers + sockets (or a channel watchable by `eventloop`), more than one channel per thread entry, channels in
  programs that also use net/files (see PAR-1 ban), docs.

### PAR-5 async I/O (non-blocking sockets/files, timers)
- **Has:** `eventloop` (library/eventloop.min): single-owner readiness loop, kqueue/epoll (runtime/native/net_loop.h),
  socket watches + timers, 8M registrations; non-blocking `net` (`readInto`, `writeRange`, `connectStart/Finish`,
  `lastErrorCode`, datagram batches/GSO). `completionio` (library/completionio.min, docs/completion-io.md): io_uring
  READ/WRITE/SYNC on regular files, Linux only. `files.syncer*`/`prepare*` background threads with a notify socket.
- **Probe:** `R/p5_async_io.min` (macOS) -> `token 7 timer false` / `accepted true` / `token 9 timer true` then
  `completionio: creating the completion queue / completion I/O failed (native code 45)` (ENOTSUP). Linux box B: same
  loop output, then `completionio available`.
- **Missing:** a composable async model (futures/async-await or at least callbacks with an executor; today every
  server hand-writes a state machine around `loop.wait`); io_uring for sockets (accept/recv/send, multishot,
  registered buffers), cancel, O_DIRECT/O_APPEND (M20 reports/systems-ioqueue.md:44-52); a portable completion backend
  (kqueue/thread-pool fallback on macOS); documented watching of non-socket fds (pipes, TUN, eventfd, pidfd); concurrent
  blocking I/O off the loop (neo-vm IMAGE-5; neo-db ADR-011); a loop per thread (blocked by the PAR-1 ban).

### PAR-6 SIMD
- **Has:** LLVM auto-vectorisation of scalar loops (loop versioning 698557809 removed range checks in matrix loops) and
  a package `cpu = "x86-64-v3"` level (docs/cli.md). Inline assembly is kernel-only with no outputs (docs/language.md
  "Inline assembly"). `--native-source NAME=FILE` links C (the escape hatch every product uses).
- **Probe:** `R/p6_simd.min` -> `error: I can't find a function named 'Float32x4'`.
- **Missing:** vector types (`Int8x16`, `Int32x8`, `Float32x8`, `Float64x4`, masks) with lane-wise arithmetic,
  compares/selects, shuffles, horizontal reductions, loads/stores from Bytes at an offset (checked once per vector),
  lowering to LLVM vector IR for SSE/AVX2/AVX-512/NEON, and runtime CPU-feature dispatch (multiversioning).

## Register

`id | gap | who hit it | severity | status at 3832f4373 | smallest repro | what closing it needs | closure test | used in project`

Severity: **B** = blocks a project (lost scope, or carries a C shim / unsafe workaround), **W** = cheap Minyar-level
workaround, **N** = nice-to-have. Status: open / partial / closed (with proof).

### Parallelism and concurrency
| id | gap | who hit it | sev | status | repro | closing needs | closure test | used in project |
|---|---|---|---|---|---|---|---|---|
| PAR-1 | No threads that can own managed state and do I/O; thread programs may not use net/files/eventloop/io/system at all | neo-db docs/adr/001-single-threaded-event-loop.md:11, adr/011:8, README.md:79 (one core per DB; TPC-B/TPC-C rows one core vs eight, R25 reports/neodbcore.md:125); minyar-wg README.md:126-133 (1.34 vs 5.39 Gb/s); Minyar-OS os/kernel/system/processors.min:3-16; minyar-proxy benchmarks/README.md:20; neo-cloud services/queue/README.md:8; minyar-sim docs/distributed.md:592; neo-vm IMAGE-5 | B | partial: every thread may own sockets/files/eventloops and main may use them (3c07696af), typed sendable entry arguments and closures (8f98278e9) / missing: shared frozen managed graphs beyond FrozenBytes | R/t6_thread_plus_net_main.min, R/t8_thread_with_*.min, R/t2_thread_shape.min | lift the whole-program effect ban (per-thread ownership of handles), richer entry signatures, shared frozen managed graphs, docs | check-thread-programs (+tsan), check-thread-compiler | |
| PAR-2 | No general work-stealing task pool (fork-join, typed tasks, ordinary callees) | neo-db R25 NEWS.md:842-855 (per-chunk engine could not run in a safe loop), FINAL-SUMMARY-search.md:35 (pg_search wins 8-client top-10 2.5-8.6x); minyar-query docs/architecture.md:14-17 (Text ops sequential) | B | partial: work-stealing pool with nested join (9f01b7467), join over ordinary functions building managed values (f823d6ff3, 44a8cd6a2), span writes for in-place divide and conquer (bdfabc96a) / missing: managed tasks in `parallel for` bodies, closures/futures, cancellation | R/p2_fork_join.min | task pool API on the existing pthread pool; ordinary callees/records in parallel bodies (needs per-thread ownership) | check-parallel-join (+tsan), check-parallel-pool | |
| PAR-3 | Atomics: only seq-cst add on raw addresses; CAS only UInt32 on Linux native regions | minyar-infer native/kernels.c:7 (`stdatomic.h` in a C kernel); Minyar-OS processors.min:16 (shared state as raw Integer addresses, 59 raw load/store calls) | B | partial: `AtomicInteger`/`AtomicBoolean` cells with per-operation orderings, weak/strong CAS, fences and futex/ulock wait/notify (82af474f4) / missing: 32-bit cell type, atomics as `parallel function` parameters | R/p3_atomics.min, R/p3b_cas.min, R/t4_native_regions.min | `Atomic<T>` cells + full ordering set + wait/notify, usable from threads and parallel bodies, macOS too | check-thread-programs (atomics.min, +tsan) | |
| PAR-4 | Channels: only Bytes, bounded, one per thread, no select, undocumented; documented ones are process round trips | minyar-wg docs/crypto-workers.md:5 (uncommitted: parallel AEAD via worker processes with copied frames); O18 status/parallel.md:11 (typed channels never started); M20 reports/concurrency.md:15 | B | built: 8f98278e9, 210efdbe4 on goal/2026-10-30 (parallel) | R/t3_thread_pool.min, R/p4_channels.min | typed move channels, select (incl. eventloop integration), docs | check-thread-programs (typed-channels.min, +tsan) | |
| PAR-5 | Async I/O: hand-written readiness loops only; io_uring files-only and Linux-only; no concurrent blocking I/O | neo-vm docs/minyar-gaps.md IMAGE-5 + image/README.md:114 (lazy image reads single-threaded); neo-db adr/011 (hand-sliced checkpoints); M20 reports/systems-ioqueue.md:44-52 | B | partial: allocation-free `eventloop.waitInto`/`updateInterest` (f8036f1e6), streaming keep-alive http client (e1f1f9809) / missing: composable async model, io_uring sockets, macOS completion backend, documented non-socket fd watching | R/p5_async_io.min | async model + socket io_uring + macOS backend + documented fd watching | check-net-loop, check-http-client | |
| PAR-6 | No SIMD types or intrinsics | minyar-wg native/fastcrypto.c:1-3 (uncommitted libsodium provider), M20 reports/vpn-profile-codegen.md:19-21; minyar-infer native/kernels.c (`immintrin.h`, dot_avx2 37-70% of time); neo-db docs/r2/search.md:24-27 | B | open | R/p6_simd.min | vector types + LLVM vector lowering + feature dispatch | | |
| PAR-7 | Thread feature (threads, BytesChannel, FrozenBytes, NativeRegion atomics) is undocumented, so products believe Minyar has no threads | neo-db, minyar-wg, minyar-proxy all say "no threads"; only neo-vm (vmm/kvm.min:154) uses it | W | built: 3c07696af, 8f98278e9, 82af474f4 on goal/2026-10-30 (parallel) | `grep -rn 'thread function' docs/` -> nothing | docs/language.md section + example + limits | check-thread-programs | |
| PAR-8 | `parallel for` bodies cannot use atomics or any native effect; parallelEntry needs raw Integers; native parallel functions scalar-only | R25 NEWS.md:880-881 (parsearch) | N | partial: atomic cells captured and used in `parallel for` bodies (82af474f4) / missing: atomics as `parallel function` parameters, vetted native effects | R/p3_atomics.min | allow vetted atomics/effects in parallel bodies | check-thread-programs (atomics.min) | |
| PAR-9 | Plain `exit` can deadlock during parallel pool shutdown (only `minyar_failure_exit` `_Exit` safe) | O18 status/parallel.md:11 | N | partial: exit from inside pool work no longer waits for its own job in atexit shutdown (9f01b7467) / missing: dedicated regression test | — | pool shutdown on exit path | check-parallel-pool | |
| PAR-10 | Restricted threads missed their 8-core scaling gate (7.075x median vs 7.2x) | T3 "Minyar: real threads" mcp:cd682ca1 (2026-10-13) | N | open per thread notes | — | profile scaling | | |
| PAR-11 | minyar-infer: 8 threads slower than 1 (10.17 -> 7.79 tok/s) | M20 reports/infer.md:35-42 | N | open, cause not attributed | — | profile with real threads/atomics once PAR-1/3 exist | | |

(rows continue below)

### Systems / standard library (server and tool products)
| id | gap | who hit it | sev | status | repro | closing needs | closure test | used in project |
|---|---|---|---|---|---|---|---|---|
| SYS-1 | Signals beyond SIGTERM/SIGINT (SIGHUP reload, SIGUSR1, SIGCHLD) need a C handler | minyar-proxy src/control.c:8-10 (`--native-source proxy=src/control.c`); minyar-terminal native/host.c:16; minyar-wg native/platform.c | B | open: `system.shutdownSignalSocket` covers TERM/INT only (library/system.min:15-18) | `system` has no general signal API (see library/system.min) | `system.signalSocket([signals])` / eventloop signal registration (signalfd/kqueue EVFILT_SIGNAL) | | |
| SYS-2 | No PTY API (openpty, spawn on controlling tty, TIOCSWINSZ resize) | minyar-terminal native/pty.c, src/pty.min:12-21, docs/pty.md:118 | B | open (`system.spawnSession` exists, no pty) | API absent | `system.openPty`, `spawnOnPty`, `resizePty`, readiness via eventloop | | |
| SYS-3 | No file locking (flock / lock file) | minyar-objstore src/platform.c:28 | B | open | API absent in library/files.min | `files.lock(file, exclusive, wait)` | | |
| SYS-4 | No path canonicalisation, file identity (dev:ino) or secure temp dir (mkdtemp) | minyar-browser src/paths.c:25,58,96; minyar-objstore src/platform.c:33 | B | open | API absent in library/files.min | `files.realPath`, `files.identity`, `files.makeTemporaryDirectory` | | |
| SYS-5 | No UTC calendar/date formatting (HTTP-date, ISO-8601) | minyar-objstore src/platform.c:39 (gmtime_r/strftime) | B | open (only `system.wallClockMicroseconds`) | API absent | civil-time conversion + RFC 7231/ISO formatting in a `time` module | | |
| SYS-6 | No MD5, base64, CRC32, CRC64 in the stdlib | minyar-objstore README.md:66-67, src/crc64.c, OpenSSL link | B | partial: `checksum.crc32c` and `text.hex` (1d3b5ad3a, 60d1ccbd9) / missing: base64, crc32, crc64, md5 | API absent | `encoding.base64`, `checksum.crc32/crc32c/crc64`, `crypto.md5` (legacy) | check-crc32c | |
| SYS-7 | No TUN device, SO_MARK, TAI64N; batched UDP over borrowed buffers | minyar-wg native/platform.c:22-26, src/platform.min:16,69,96; native/batch.c (uncommitted), docs/batching-design.md:15 | B | open (net datagram batches copy and allocate per call) | API absent | `net.openTun`, socket options, zero-copy mmsg into caller Bytes | | |
| SYS-8 | No stdin line reader | M20 reports/showcase-game-notes.md:11-14 (14-line C getchar adapter) | B | open | R/x3_stdin.min -> `module 'io' has no function named 'readLine'` | `io.readLine()` / stdin Bytes reads | | |
| SYS-9 | FFI rejects raw pointers, opaque handles and callbacks; Lists cannot cross the native ABI | M20 reports/ffi-research.md:36-42; minyar-terminal docs/pty.md:125-126; every C adapter packs argv as Bytes | B | open (C header import aec7debfc: scalars/records only) | — | pointer/handle types with explicit lifetime; List<Text> marshalling | | |
| SYS-10 | Freestanding runtime has no sockets/clock; edge built its own unikernel HTTP path; OS runtime fixes live on the Minyar-OS branch | M20 reports/edge-os-research.md:35-40; minyar-edge unikernel/README.md:21-24 | B | open per notes, not re-tested | — | freestanding net/clock providers in the SDK | | |
| SYS-11 | Heap memory not returned to the OS after a burst | neo-db minyar-gaps/r2-server.md (R2SRV-1) | W | partial. Linux box B: eager profile 52524 -> 22260 kB after `releaseFreeMemory` (baseline 2084 kB); default `system` profile 52524 -> 52524 kB (nothing returned); macOS: `releaseFreeMemory` returns 0, RSS 52336 -> 52336 kB | R/r2srv_heap_trim.min | runtime small-heap page release (madvise) on every platform | | |
| SYS-12 | `print` has no flush; line acks need unbuffered output | minyar-proxy src/control.c:37 (`fflush(stdout)` in C) | W | partial: `files.writeStandardOutput` writes unbuffered (library/files.min:52) | — | `io.flushOutput()` or documented print buffering | | |
| SYS-13 | No ext4 image writer (host `sudo mkfs.ext4`) | neo-vm image/build.min:140, docs/minyar-gaps.md IMAGE-4 | W | partial: erofs writer closed (library/erofs.min), ext4 open | — | ext4 writer (or keep host tool) | | |
| SYS-14 | Watching foreign fds (TUN, pipes) in eventloop undocumented | minyar-wg src/platform.min:61 (poll in C) | N | unknown: epoll/kqueue path accepts any pollable fd (runtime/native/net_loop.h:355-380) but docs say "sockets" | — | document + test non-socket fds | | |
| SYS-15 | seccomp filter construction | neo-vm isolation/neovm-seccomp.md:72-74 ("likely a Minyar gap") | N | not confirmed; done with raw syscall + Bytes (vmm/seccomp.min) | — | — | | |
| SYS-16 | `clock_gettime` failures unchecked in worker/system clocks | M20 reports/concurrency-workers-research.md:62 | N | not re-tested | — | check return codes | | |
| SYS-17 | No SQLite binding / vsock in `net` (sandbox host integration stays Python) | minyar-sandbox AGENTS.md:18, README.md:367 | N | open (sequencing, not blamed on Minyar) | — | — | | |
| SYS-18 | No HTTPS listener: `http.listenTLS(host, port, limits, identity, key)` (the TLS server session and the HTTP server exist, nothing joins them) | minyar-objstore src/main.min:36 (E0302: module 'http' has no function named 'listenTLS'; project does not build) | B | in progress: run-2 lane `tls`, branch goal/r2-tls (4200478e8 + tests), objstore served over HTTPS with the tree in the lane report | `minyar build --release` in minyar-objstore | `http.listenTLS` in library/httpserver.min + O0/O2 TLS client round-trip tests | | |
| SYS-19 | Six other Minyar projects no longer build against v2: `Text(bytes)` → `text.decode`/`text.decodeOrStop` (v2 4780f06e7, 2026-10-26; 27 call sites in 8 projects) | real-world suite, reports/run2/rw.md (minyar-query, -sandbox, -sim, -terminal, -js and others) | W | open for the owning loops (FYI row in ~/Projects/goal-loops/REQUESTS.md); minimal patches in benchmarks/realworld/adoption/*.patch | `python3 benchmarks/realworld/run.py --tree .` | each project adopts `text.decodeOrStop` (owner loops) | | |

### Language, runtime and correctness
| id | gap | who hit it | sev | status | repro | closing needs | closure test | used in project |
|---|---|---|---|---|---|---|---|---|
| LANG-1 | Out of memory and call-depth exhaustion cannot be contained; `boundary.run` also excludes runtime-called code (comparators, Map hash/equal, parallel bodies, threads) | neo-db G14 (parser caps nesting at 1000, docs/MINYAR_GAPS.md:117-121), R25 NEWS.md:1371-1376 (extensions); minyar-safelibs M20 reports/safelibs-oom-next-notes.md:7-14 (C drop-in needs malloc failure as error) | B | partial: guard pages detect stack exhaustion with the same message and exit status at zero per-call cost (c0b4b1e97) / missing: containment inside `boundary.run`, depth/OOM as recoverable failures, remaining-depth query | R/g14_call_depth.min, R/g14_depth_boundary.min (boundary.run still stops: "exceeded the maximum call depth") | depth/OOM as contained failures inside boundary.run; remaining-depth query | check-stack-overflow, check-stack-limits | |
| LANG-2 | Unknown text escapes accepted silently: `"\u{2022}"` prints `u{2022}`, `"\u{0}"` is 4 bytes | minyar-render M20 reports/render-claude.md:106-111; minyar-browser; minyar-terminal reports/terminal.md:11; Minyar's own tests/net-connect.min | W (silent wrong output) | open | R/x2_unicode_escape.min -> `u{2022}` / `4` | `\u{HEX}` escape + reject unknown escapes | | |
| LANG-3 | `deterministic (A) -> B` widens to `(A) -> B` only for bare names, not member paths | neo-db D8 merge, R25 NEWS.md:1546-1556 (SDK split invoke/invokeVolatile) | W | open | R/x1_deterministic_member_widen.min -> E0401 twice | widen at every expression form | | |
| LANG-4 | Generic functions are not values; closures cost ~1k instructions; fused sequence transforms need named functions | neo-db ext host R25 NEWS.md:1109-1110,1459-1461; M20 reports/showcase-atlas-notes.md:34 | W | open | R/x5_generic_value.min -> `I can't find a value named 'identity'` | instantiate generics at function-value use; cheaper closure environments | | |
| LANG-5 | No arbitrary-precision integers / exact decimal | minyar-sandbox README.md:287-289 (rate cap); minyar-query README.md:31 (Float64 only) | N | open | — | `BigInteger`/`Decimal` library | | |
| LANG-6 | Statement temporaries are not released when a callee stops the program (LSan 24 B) | R25 NEWS.md:1562-1571 (check-osdev-fields-sanitize red) | N | open | per notes | ownership decision for stop paths | | |
| LANG-7 | No Printable capability (records/Lists need explicit Text in interpolation) | O18 status/text.md:8 | N | open | — | Printable capability | | |
| LANG-8 | Runtime stop locations imprecise (declaration, not call site) | O18 status/diagnostics.md:10 | N | not re-tested | — | — | | |
| LANG-9 | No zero-allocation Boolean overflow check for hot paths (checked builtins return Result) | neo-db docs/MINYAR_GAPS.md:173 | N | open per notes | — | `addOverflows(a, b): Boolean` style intrinsics | | |
| LANG-10 | Freestanding: no distinct physical/virtual address types; assembly clobbers are an author promise; no annotation to vouch a native as interrupt-safe | Minyar-OS M20 NEWS.md:1136, FINAL-SUMMARY.md:35, reports/osdev2.md:60 | N | partial (typed device addresses b58d88839) | — | — | | |

### Performance gaps that cost a project its target (owned by the perf lanes; listed for completeness)
| id | gap | who hit it | sev | status | repro | closing needs | closure test | used in project |
|---|---|---|---|---|---|---|---|---|
| PERF-1 | Ownership/RC bookkeeping dominates allocation-heavy and numeric code | minyar-js M20 reports/jsengine-claude.md:97-104 (~58% of start-up; 1.07 vs QuickJS 0.47 ms); minyar-infer reports/infer-profile-codegen.md:10-13 (20-47%); neo-db G13 field borrows | B | partial (R25 borrow elision f944f2f8b etc.; not re-measured on js/infer) | R/g13_default_cleanup_cost.min | perf lanes | | |
| PERF-2 | Default `system` profile slower than eager on allocation-heavy code | neo-db G13 (was 2.5-3.7x), R25 NEWS.md:211-217 (YCSB up to 12x) | W | partial: re-measured here 7.88 G vs 6.71 G instructions (1.17x), 493 vs 397 ms (n=3, spread < 3%); `memory = "eager"` key b977bac0d | R/g13_default_cleanup_cost.min | perf lanes | | neo-db uses eager |
| PERF-3 | Checked Bytes get/set dominate codec/byte loops (12-28x C codecs; objstore 32% in minyar_bytes_set; c2min jsmn 30-270x C) | minyar-safelibs/objstore/c2min M20 FINAL-SUMMARY.md:30,59-60, NEWS.md:959 | B | partial (inlined checked access 711861bca) | — | perf lanes | | |
| PERF-4 | Every `Ok` allocates a Result record (`text.decode` +710-825 instructions) | R25 reports/lang.md:123-126 | N | open | — | niche/in-register Result | | |
| PERF-5 | Tail latency: big drops paid inside requests; old-backlog pacing is opt-in | minyar-edge/neo-db R25 reports/edge.md:150-157, FINAL-SUMMARY-run2.md:60 (A23) | W | partial (mechanism 93f877ddb, default off) | — | launcher setting / default | | |
| PERF-6 | No link-order (symbol ordering file) option; idle PSS 2.9 MiB vs 2 MB target | neo-db R25 reports/neodbcore.md:68-74,123-124 (scoreboard row 4 missed) | B | open | — | `--order-file` / startup-contiguous link | | |
| PERF-7 | Patchable (hot) builds cost ~+8.6% instructions per request | R25 FINAL-SUMMARY.md:47 | N | open | — | — | | |

### Tooling
| id | gap | who hit it | sev | status | repro | closing needs | closure test | used in project |
|---|---|---|---|---|---|---|---|---|
| TOOL-1 | `minyar fmt` drops Map-literal commas, producing code that no longer compiles | contracts lane M20 NEWS.md:299 | W | open | R/x6_fmt_map_comma.min compiles (42, 2); `minyar fmt --stdout` output R/x6b_fmt_output.min -> `error: expected ',', found 'b'` | grammar-aware brace roles in the formatter | | |
| TOOL-2 | Live patch needs a restart for signature/record changes, new native libs | R25 NEWS.md:975-980; M20 FINAL-SUMMARY.md:39 | N | open by design (additive patches fd79fd727) | — | — | | |
| TOOL-3 | Generic stdlib imports drop builds out of incremental mode; no cached instantiations | O18 status/results.md:9, status/generic.md:8 | N | not re-tested | — | — | | |
| TOOL-4 | `minyar explain` has no machine-readable output; `minyar test` has no expectFailure | M20 reports/showcase-clinic-notes.md:80-82; O18 status/testdoc.md:17 | N | open per notes | — | — | | |
| TOOL-5 | Products pinned to old Minyar still carry workarounds for gaps that are closed upstream | neo-cloud services/queue/README.md:203 (pinned 031e8ab: no fsync, no env, own Map, own JSON quote; topic service written in TypeScript, MORNING.md:98); minyar-query docs/first-proof.md:154-160 (`reduce` workaround, fixed 0546eee93); neo-db WAL zero-fills on the loop although `files.prepare*` exists | W | open (product work, not Minyar) | — | re-pin and drop workarounds | | |

### Requests filed in ~/Projects/goal-loops/REQUESTS.md (added by the orchestrator, 2026-10-30)

| id | gap | who hit it | sev | status | repro | closing needs | closure test | used in project |
|---|---|---|---|---|---|---|---|---|
| REQ-1 | `minyar test` doc reader rejects `deterministic` callable record fields | neo-db orchestrator (REQUESTS 2026-10-30) | B | closed on goal/2026-10-30: cherry-picked f403c8ab0 → f403c8ab0 (+ fixture re-pin a9e4ef811) | neo-db tests/engine/values_test.min via `minyar test` | merge neodb-d8-integration-merge | tests/doc-comments.min (check-doc-comments) | neo-db pins 67b00af (same fix) |
| REQ-2 | `tls.clientWithTrust` capped at 16 DER anchors / 1 MiB; `http` has no custom-trust / SSL_CERT_FILE option | neo-db import | W | built: ac22befd2, c26af6a9d on goal/2026-10-30 (systems) | neo-db src/engine/import/remote.min | lift anchor cap or accept PEM bundle path; trust option on http.fetch* | check-tls (tls-protocol, tls-local-test) |  |
| REQ-3 | `http` buffers whole responses (128 MiB cap), one connection per request: no streaming body or keep-alive | neo-db import | B | partial: portable `http` Client streams bodies over a kept connection (e1f1f9809) / missing: the same Client shape on macOS | neo-db src/engine/import/remote.min | streaming body reader + keep-alive connection pool in `http` | check-http-client, check-tls (tls-local-test) |  |
| REQ-4 | `math` lacks sinh/cosh/tanh/asinh/acosh/atanh/erf/erfc/expm1/log1p/cbrt (libm-exact) | neo-db compat-a | W | built: a3abe0ad5 on goal/2026-10-30 (stdlib) | `math.sinh(1.0)` missing | bind libm | check-math-library |  |
| REQ-5 | Compiler front end peaks ~6.85 GB RSS building neo-db --release | neo-db orchestrator | B | open | box B `minyar build --release` of neo-db, /usr/bin/time -v | cut front-end memory (arena reuse, streaming per-module emission) |  |  |
| REQ-6 | No package option for release link layout: symbol ordering file / profile-ordered start-up code, extra link flags | neo-db memory (idle PSS ≤ 2.0 MiB target) | B | open | neo-db ops/run25/env.sh MINYAR_CLANG_FLAGS hack | Minyar.toml link options + lld --symbol-ordering-file (or automatic start-up ordering) |  |  |
| REQ-7 | `tls` natives link -lcrypto eagerly (+450 KiB PSS per idle process) | neo-db memory | B | built: e1fc31110, f03a3527e on goal/2026-10-30 (systems) | neo-db ops/memory/lazycrypto.sh | dlopen libcrypto on first use | check-lazy-crypto |  |
| REQ-8 | Start-up data layout: per-function literal sections; no load-time pointer fixups for function-value constants | neo-db memory | W | open | neo-db ops/memory/respages.py | section naming + relative function tables |  |  |
| REQ-9 | Module globals initialised eagerly before main; no hot/cold splitting of large functions | neo-db memory | B | open | neo-db hand-written `if T.length == 0` fills | lazy module globals (no per-read cost after init) + hot/cold splitting in release |  |  |
| REQ-10 | `math.toFloat32` intrinsic; small helpers not inlined (call-depth counter per call) | neo-db search | W | partial: `math.toFloat32` (a3abe0ad5) and the per-call depth counter is gone, so small helpers inline (c0b4b1e97) / missing: helpers around global Bytes methods still stay out of line (retain/release) | neo-db extensions/vector/src/float4.min before 93c6e5c | intrinsic + inline small functions / drop call-depth bookkeeping | check-math-library, check-stack-overflow |  |
| REQ-11 | `Bytes.addRange(other,start,end)`; `files` stat (kind+size) | neo-db export | W | built: a3abe0ad5 on goal/2026-10-30 (stdlib) | neo-db src/engine/export | add APIs | check-stdlib-everyday |  |
| REQ-12 | CRC32C intrinsic usable from parallel functions (SSE4.2 / ARMv8 crc32) | neo-db storage (recovery floor) | B | built: 1d3b5ad3a on goal/2026-10-30 (systems) | neo-db src/storage/crc32c.min | `bits.crc32c` lowered to hardware crc32 with table fallback | check-crc32c, check-parallel-for |  |
| REQ-13 | `files.link` (hard link) and an fsync (not fdatasync) syncer mode | neo-db branching | B | built: 34babb63d, a3abe0ad5 on goal/2026-10-30 (systems, stdlib) | neo-db src/server/branch.min, src/storage/datafile.min | add files.link + syncer fsync mode | check-files |  |
| REQ-14 | `parallel for` cannot write to element i of a captured List<Bytes> or grow it | neo-db storage (recovery) | B | partial: a join per range returning `List<Bytes>`, concatenated with `List.addAll` (f823d6ff3, 44a8cd6a2, 07605c7cd) / missing: per-iteration owned List<Bytes> elements incl. growth inside `parallel for` | neo-db src/engine/table.min appendDecodedRow | per-iteration ownership of distinct List elements incl. growth | check-parallel-join |  |
| REQ-15 | Allocation-free `eventloop.wait` / `update` | neo-db oltp (TPC-B ≥ 1.0× PG) | B | built: f8036f1e6 on goal/2026-10-30 (systems) | callgrind ops/oltp/cg.sh | caller-owned event buffer API | check-net-loop |  |
| REQ-16 | `files` syncer inline sync when idle, drain stops after short read, no F_GETFL per writeAt | neo-db oltp | B | built: 34babb63d on goal/2026-10-30 (systems) | strace -c -f under pgbench -c1 | syncerSyncNow + syscall trimming | check-files |  |
| REQ-17 | Cheaper reclamation of short-lived values; module-global read ~37 instructions | neo-db oltp | B | partial: borrow-free global reads (0ca8a7edd), `try` consumes fresh Results (72b81df5a), all-scalar choices as scalar records (15763d412) / missing: heap Result allocation per `Ok`, statement temporaries, bounded scheduler unit cost | callgrind pgbench TPC-B | see ownership lane | check-stable-field-borrows, check-result-try-consumption, check-match-payload-borrows |  |
| REQ-18 | One cycle-capable List mutation spreads scope/cycle service points into every hot function | neo-db tpch | B | open (ownership lane) | neo-db 572ae54 vs fb788d9 | confine tracing to the traced component + build warning naming the statement |  |  |
| REQ-19 | `files` O_DIRECT/O_DSYNC with aligned Bytes, and `fallocate` | neo-db storage (write amplification) | B | partial: `files.DIRECT`/`files.DATA_SYNC`, `files.directAlignment` and `files.preallocate` (34babb63d) / missing: a user-facing aligned Bytes allocator | neo-db ops/storage/wa_probe.py | open flags + aligned buffers + fallocate | check-files |  |

### Closed: gaps fixed at or before 3832f4373 (re-tested here)
| id | gap | who hit it | proof at 3832f4373 | used in project |
|---|---|---|---|---|
| ND-G1 | append/fsync/rename/directory sync | neo-db minyar-gaps/g1_fsync.min | library/files.min:68-100 (`syncData`, `sync`, `rename`, `syncDirectory`) | neo-db (native/dbio.c deleted) |
| ND-G3 | wall clock | neo-db | `system.wallClockMicroseconds` (library/system.min:7) | neo-db |
| ND-G5 | SIGTERM/SIGINT as events; SIGPIPE | neo-db g5_signals.min | `system.shutdownSignalSocket/drainShutdownSignals/ignoreBrokenPipes` (library/system.min:15-18) | neo-db |
| ND-G6 | SO_REUSEADDR on listen | neo-db g6, neo-cloud | R/g6_listen_reuseaddr.min: second listen returns 3 (was -1) | neo-db |
| ND-G7 | accept would-block vs error only via strerror | neo-db g7, neo-cloud | `net.lastErrorCode()` (library/net.min:41) | neo-db |
| ND-G8 | read allocates + zero-fills | neo-db g8 | `net.readInto`, `net.writeRange` (library/net.min:45,48) | neo-db |
| ND-G9 | no stderr | neo-db g9 | `system.writeStandardError` (library/system.min:23) | neo-db |
| ND-G10 | no rlimit | neo-db g10 | `system.raiseOpenFileLimit/getSoftLimit/setResourceLimit`; R/g10_no_rlimit.min opens 5000 | neo-db |
| ND-G11 | module constant tables | neo-db g11 (CRC32C table) | docs/language.md "Immutable Integer tables", "Runtime globals"; R/g11_module_tables.min | — |
| ND-G12 | List truncate/pop | neo-db list_truncate, neo-cloud, neo-vm VMM-6 (clear) | R/list_truncate_pop.min -> `2`/`1`; R/list_clear.min -> `0` (5dadee870) | — |
| ND-G15/G16 | overflow, index, division stop the server | neo-db G15/G16 | R/g15_overflow_boundary.min -> `true` / `still serving` (boundary.run e81b2f51d + checked builtins) | neo-db sdk/src/neodb-sdk.min:102 |
| ND-G17 | `Text(bytes)` stops on bad UTF-8 | neo-db | `text.decode` Result (4780f06e7) | neo-db (migrated) |
| ND-G18 | Unix sockets + SCM_RIGHTS | neo-db G18, R25 A8 | c9a61886d, docs/language.md:1696-1711 | not yet (neo-db still per-shard ports) |
| ND-G2/VMM-3 | user packages cannot link C | neo-db G2, neo-vm vmm-3 | `--native-source`, `--native-object` (./minyar --help) | neo-vm, proxy, objstore, wg, terminal |
| ND-G4/IMAGE-2 | Map, sort | neo-db, neo-vm, neo-cloud | R/c_map_sort.min -> `true`/`1` | neo-vm, neo-db |
| ND-R2S-1 | 16 syncers per process | neo-db | R/r2s_syncer_limit.min -> `started 100 syncers` | neo-db |
| ND-R2S-2 | positioned read into existing Bytes | neo-db | `files.readAppend` (library/files.min:62) | neo-db |
| ND-R2SRV-2 | rmdir | neo-db | `files.removeDirectory` (library/files.min:170) | neo-db |
| ND-PREP | background file preallocation | neo-db docs/MINYAR_GAPS.md:13 | `files.prepareStart/Wait/Stop` (library/files.min:157-168) | not yet (neo-db zero-fills on loop) |
| VMM-1 | raw syscall | neo-vm | `machine.syscall` (library/machine.min:17) | neo-vm 3fb2dc0 |
| VMM-2 | thread that blocks in the kernel (KVM_RUN) | neo-vm | `thread function` + `threadKernelRun` (tests/thread-fixtures) | neo-vm 4d41b10 (C vCPU shim deleted) |
| VMM-4 | C-layout records | neo-vm | R/c_c_layout.min (`record X native "c"`, sizeOf/offsetOf/cView) -> `16 12 8` | neo-vm |
| VMM-5 | silent built-in name reservation | neo-vm | R/c_builtin_name.min: clear E0502 with rename hint; docs/language.md "Reserved function names" | — |
| GUEST-1 | octal literals | neo-vm octal.min | R/c_octal.min: `0o755` ok, `0755` rejected (E0104) | neo-vm |
| GUEST-3 | process spawn/wait | neo-vm fork-spawn.min | R/c_spawn.min -> `spawned` / `0` | neo-vm |
| GUEST-4 | Text split/startsWith/parse | neo-vm text-split.min | R/c_text_split.min -> `70`/`true`/`70` | — |
| ADAPTER-1 | getenv | neo-vm, neo-cloud | R/c_getenv.min -> `true` | — |
| IMAGE-1 | gzip/zstd | neo-vm | library/deflate.min, library/zstd.min | neo-vm image/lazy.min:18 |
| IMAGE-3 | slow/copying sha256 | neo-vm (own 314 MB/s) | R/c_sha256_speed.min -> 2117 MB/s over 256 MiB (openssl dgst: 0.17 s) | — |
| IMAGE-4a | erofs writer | neo-vm | library/erofs.min | neo-vm image/build.min:3 |
| NC-JSON | json.quote turned controls into spaces | neo-cloud | library/json.min:483 hex escapes | not re-pinned |
| R25-A1 | -O1/-O2 wrong Boolean (zeroext) | neo-db parsearch | 053c77a5b + check-miscompiles | neo-db (mask workaround revertible) |
| R25-A3 | parallel for: buffers, List<Bytes>, windows, records | neo-db parsearch | c442bb34c, f094962b1, 5c51fa258 | neo-db src/search/index.min:3185 |
| R25-A4/A5 | named functions as callbacks; deterministic callables | neo-db ext | f24bb0cd2, b1ca248df | neo-db SDK |
| R25-A9 | contained plugin failures | neo-db ext | e81b2f51d | neo-db SDK |
| R25-det-par | determinism proof rejected safe parallel for | neo-db sim | 121ed1974 | neo-db sim |
| M20-reduce | `reduce` rejected after `use "process"` | minyar-query | 0546eee93 | not yet (workaround kept) |
| M20-STATE | imported module `STATE.field` | concurrency/livedx | c9906d3e0 | — |
| M20-some-try | `Some(try ...)` leak | concurrency | 8a51cc477 | — |
| O18-recv | members named sendBytes/receiveBytes lexed as thread builtins | results lane | R/x4_thread_builtin_member.min -> `2` | — |
| GUEST-2 | spawned children inherit SIGPIPE ignored | neo-vm sigpipe-inherit.min | Linux box B R/c_sigpipe_child.min: child `SigIgn: 0000000000000000` | neo-vm (resetChild workaround can go) |
| ND-io_uring | no io_uring binding (neo-db ADR-005) | neo-db | `completionio` (aaa09c175); Linux box B `completionio available` | not yet |


## Summary

### Counts (rows in this register)
| severity | open | partial | not re-tested / unconfirmed | total open-ish | closed |
|---|---|---|---|---|---|
| B blocks a project | 14 (PAR-6, SYS-1..10, SYS-18, LANG-1, PERF-6; SYS-10 from notes) | 7 (PAR-1..5, PERF-1, PERF-3) | 0 | 21 | — |
| W workaround | 7 (PAR-7, SYS-19, LANG-2..4, TOOL-1, TOOL-5) | 5 (SYS-11..13, PERF-2, PERF-5) | 0 | 12 | — |
| N nice-to-have | 12 | 1 (LANG-10) | 6 (PAR-9, SYS-14..16, LANG-8, TOOL-3) | 19 | — |
| closed at 3832f4373 | | | | | 42 (nearly all were B when filed: C shims in neo-db/neo-vm, lost scope in neo-db search) |

Total 92 rows: 50 open or partial, 42 closed. At least 6 closed rows are not yet used by the product that asked for
them (neo-db: Unix sockets/SCM_RIGHTS, prepare jobs, io_uring; minyar-query: the `reduce` fix; neo-cloud: still pinned to
031e8ab, so none of its closed gaps incl. JSON quote; neo-vm: can drop its SIGPIPE reset) — see TOOL-5.

### Top 10 "blocks a project" items, suggested build order (parallelism first)
1. **PAR-1 + PAR-7: make the existing threads usable and documented.** Lift the whole-program effect ban so a thread
   program can use net/files/eventloop/io/system (each handle owned by one thread), allow several channels and moved
   records/Text/Lists at thread entry, add shared frozen managed graphs, and write the docs/language.md section.
   Unlocks neo-db thread-per-core shards (ADR-001), minyar-wg/minyar-proxy multi-worker, Minyar-OS SMP beyond pixels.
   Smallest closure tests: `R/t6_thread_plus_net_main.min` compiles and runs; `R/t2_thread_shape.min` variant with a
   moved record.
2. **PAR-3: atomics.** `Atomic<Integer>` (and Boolean/pointer-free cells) in managed records/globals shared with threads
   and parallel bodies; load/store/exchange/CAS (strong, weak, 64-bit)/fetch ops; relaxed..seq_cst orderings; fences;
   futex-style wait/notify; macOS. Closure: `R/p3_atomics.min` and `R/p3b_cas.min` compile and print exact counts.
   Replaces minyar-infer's `stdatomic.h` and Minyar-OS raw-address sharing.
3. **PAR-4: typed channels + select.** Move any owned value (not only Bytes), bounded/unbounded, MPMC, close/drain, and
   `select` over channels, timers and sockets (or channels registrable in `eventloop`). Closure: a typed version of
   `R/t3_thread_pool.min` plus a select test. Replaces minyar-wg's worker-process crypto plan.
4. **PAR-2: work-stealing task pool.** Submit typed tasks/closures to the existing pthread pool, nested fork-join,
   futures with results and cancellation; ordinary callees and record field writes in parallel bodies once ownership is
   per thread. Closure: `R/p2_fork_join.min` compiles and prints `499999500000`. Unlocks neo-db per-query parallelism
   (disjunction/phrase top-k) and minyar-query Text operators.
5. **PAR-5: async I/O across threads.** One `eventloop` per thread, io_uring sockets (accept/recv/send multishot,
   registered buffers, cancel), a macOS completion backend, a composable async layer over the loop, and concurrent
   blocking I/O off the loop (neo-vm IMAGE-5, neo-db sliced checkpoints ADR-011).
6. **PAR-6: SIMD.** Vector types with lane ops, masks, shuffles, reductions, checked vector loads from Bytes, LLVM vector
   lowering and runtime feature dispatch. Closure: `R/p6_simd.min` compiles; minyar-wg ChaCha20 and minyar-infer dot
   kernels move out of C.
7. **LANG-1: contained OOM and call-depth failures** (and runtime-called code inside `boundary.run`). Closure:
   `R/g14_depth_boundary.min` prints `true` / `still serving`. neo-db stops capping every recursion by hand; minyar-safelibs
   can return allocation failure as an error.
8. **SYS-1: general signal subscription** (SIGHUP, SIGUSR1, SIGCHLD...) through the eventloop. Deletes the C signal
   shims in minyar-proxy (src/control.c), minyar-terminal (native/host.c) and minyar-wg.
9. **SYS-9: FFI raw pointers / opaque handles / callbacks and List<Text> marshalling.** Every product C adapter packs
   argv into Bytes and wraps handles by hand (minyar-terminal docs/pty.md:125, wg, objstore, browser).
10. **SYS-3..6: systems stdlib batch** — `files.lock` (flock), `files.realPath`/identity/`makeTemporaryDirectory`,
    a `time` module with UTC civil time + HTTP-date/ISO-8601, and base64/CRC32/CRC32C/CRC64/MD5. Deletes
    minyar-objstore src/platform.c + src/crc64.c (and its OpenSSL link) and minyar-browser src/paths.c.

Other open "blocks a project" rows not in the ten: SYS-2 PTY (minyar-terminal), SYS-7 TUN/SO_MARK/zero-copy mmsg
(minyar-wg), SYS-8 stdin readLine (showcase C adapter), SYS-10 freestanding sockets/clock (minyar-edge), and the perf
rows PERF-1 (RC bookkeeping), PERF-3 (checked Bytes access), PERF-6 (link-order option for neo-db idle PSS), which belong
to the perf lanes.

### Notes for whoever builds these
- The real-threads runtime already exists (per-domain heaps, Bytes moves, frozen Bytes, MPMC Bytes channels, native
  regions with acquire/release/CAS, TSan checks `check-thread-*`). Items 1-4 should extend it rather than start again.
  Its effect checker (compiler/thread-compiler.min, "unsafe thread effect") is what blocks every server today.
- Native regions are Linux-only (mmap flags 34 = MAP_PRIVATE|MAP_ANONYMOUS passed raw by callers); `completionio` is
  Linux-only; `releaseFreeMemory` is a no-op on macOS and returns nothing under the default `system` profile on Linux.
- Box B Linux log for this pass: `R/linux-boxB.log` (copied repros were staged as untracked
  `wt/gaps/gaps-repros/` so `bb` could sync them; nothing committed).

## Status update 2026-10-31 (bookkeeping)

Bookkeeping pass over the lane reports (`systems`, `stdlib`, `parallel`, `parallel2`, `calls`, `ownership`) and the
Status column of `goal-loops/REQUESTS.md`. No row is marked `closed`: adoption by the project is not recorded, so
`used in project` stays empty. Severities unchanged.

| id | old status -> new status | source report |
|---|---|---|
| PAR-1 | partial: undocumented `thread function` (fixed signature, Bytes-only transfer) -> partial: per-thread owned sockets/files/eventloops, typed entry arguments, closures (3c07696af, 8f98278e9) / missing: shared frozen managed graphs | parallel |
| PAR-2 | partial: flat `parallel for` + windows -> partial: work-stealing pool + nested join (9f01b7467), managed join (f823d6ff3, 44a8cd6a2), join spans (bdfabc96a) / missing: managed tasks in `parallel for`, closures/futures | parallel, parallel2 |
| PAR-3 | partial -> partial: `AtomicInteger`/`AtomicBoolean` with orderings, weak/strong CAS, fences, wait/notify (82af474f4) / missing: 32-bit cell, atomics as `parallel function` parameters | parallel |
| PAR-4 | partial -> built: 8f98278e9, 210efdbe4 on goal/2026-10-30 (parallel) | parallel |
| PAR-5 | partial -> partial: `eventloop.waitInto`/`updateInterest` (f8036f1e6), keep-alive streaming http Client (e1f1f9809) / missing: async model, io_uring sockets, macOS backend, documented fd watching | systems |
| PAR-7 | open -> built: 3c07696af, 8f98278e9, 82af474f4 on goal/2026-10-30 (parallel) | parallel |
| PAR-8 | open -> partial: atomic cells usable in `parallel for` bodies (82af474f4) / missing: atomics as parallel-function parameters, vetted effects | parallel |
| PAR-9 | not re-tested -> partial: exit from pool work no longer waits in atexit shutdown (9f01b7467) / missing: dedicated test | parallel |
| LANG-1 | open -> partial: guard-page stack-exhaustion detection, same message at zero per-call cost (c0b4b1e97) / missing: containment inside `boundary.run`, remaining-depth query | calls |
| SYS-6 | open (base64 only private in library/tar.min:157) -> partial: `checksum.crc32c`, `text.hex` (1d3b5ad3a, 60d1ccbd9) / missing: base64, crc32, crc64, md5 | systems, stdlib |
| REQ-2 | open -> built: ac22befd2, c26af6a9d on goal/2026-10-30 (systems) | systems, REQUESTS.md |
| REQ-3 | open -> partial: portable http Client streams over a kept connection (e1f1f9809) / missing: same Client shape on macOS | systems, REQUESTS.md |
| REQ-4 | open (stdlib lane) -> built: a3abe0ad5 on goal/2026-10-30 (stdlib) | stdlib |
| REQ-7 | open -> built: e1fc31110, f03a3527e on goal/2026-10-30 (systems) | systems, REQUESTS.md |
| REQ-10 | open (stdlib + codegen lanes) -> partial: `math.toFloat32` (a3abe0ad5), call-depth counter removed (c0b4b1e97) / missing: helpers around global Bytes methods still out of line | stdlib, calls |
| REQ-11 | open (stdlib lane) -> built: a3abe0ad5 on goal/2026-10-30 (stdlib) | stdlib |
| REQ-12 | open -> built: 1d3b5ad3a on goal/2026-10-30 (systems) | systems, REQUESTS.md |
| REQ-13 | open -> built: 34babb63d, a3abe0ad5 on goal/2026-10-30 (systems, stdlib) | systems, stdlib, REQUESTS.md |
| REQ-14 | open -> partial: join per range + `List.addAll` (f823d6ff3, 44a8cd6a2, 07605c7cd) / missing: per-iteration owned List<Bytes> elements incl. growth in `parallel for` | parallel2 |
| REQ-15 | open -> built: f8036f1e6 on goal/2026-10-30 (systems) | systems, REQUESTS.md |
| REQ-16 | open -> built: 34babb63d on goal/2026-10-30 (systems) | systems, REQUESTS.md |
| REQ-17 | open (ownership lane) -> partial: borrow-free global reads (0ca8a7edd), `try` consumes fresh Results (72b81df5a), scalar-record choices (15763d412) / missing: heap Result allocation, statement temporaries, scheduler unit cost | ownership |
| REQ-19 | open -> partial: `files.DIRECT`/`DATA_SYNC`, `directAlignment`, `preallocate` (34babb63d) / missing: user-facing aligned Bytes allocator | systems, REQUESTS.md |
