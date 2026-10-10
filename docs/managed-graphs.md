# Selective managed graph support (isolated candidate)

This candidate accepts formerly rejected cyclic List/record mutation. It is
kept on `feat/v2-runtime-memory` until correctness, compatibility and the
unchanged resource gates are established. Typed closures and callback dispatch
are implemented through a generated optional frontend. Process-isolated
workers use copied byte messages on macOS/Linux and Windows. Windows uses
overlapped named pipes; actual Windows CI validation is required before that
backend is ready. Shared managed threads are not implemented.

The ordinary compiler only recognizes feature syntax and requests the optional
frontend; its former two cycle-prevention sites also request that frontend.
It has no collector fixup bookkeeping. A guarded adapter derives the extended
frontend from that same core and separately maintained feature helpers.
The generated frontend emits ordinary allocation and ownership pieces first. Its
existing signature-cache tail stores typed deferred fixups and activation
roots. Only a mutation whose declared edge can return to its receiver activates
that receiver's strongly connected type component. After all bodies are
checked, selected pieces become traced allocations/stores/ownership barriers.
An unrelated recursive type component remains untraced. Code with no newly
accepted cyclic mutation emits exactly the old LLVM, including recursive
construction and JSON's bottom-up `appended` operations.

The collector is adapted from repository branch `port/astra-cycles-v2`, commit
`976a75a8c51518006cb654d6e6304f425e2eab91`. Its independent graph/root/debt oracle
is adapted from that same commit, with several deterministic generated seeds.
No peer-language test source was copied. The earlier research document records
Nim ORC and other primary-source inspirations, licenses and source hashes.

Ordinary runtime engine/header files remain byte-for-byte unchanged. A program
with activated graph components emits `; minyar-cycle-runtime: 1`; the launcher
builds a separate content-addressed runtime object. `tools/cycle_runtime.py`
renders the common engine with only the two audited RC/collection include
substitutions, so platform/runtime engine fixes still have one source. The
cycle headers are separately named and contain collector barriers; ordinary
programs have no dormant owner checks, collector branches, added metadata or
atomic reference counts. This costs maintenance in the RC/collection variants
and needs explicit consistency tests when those default files change.

Each traced allocation carries 32 metadata bytes before its unchanged eight
byte RC header, plus allocator rounding. Collection is a single-thread snapshot
of a finite allocation cohort, with root shading, owning-slot incoming counts,
gray pins and bounded work units. Work budgets are not wall-clock deadlines.
Compiler-private and native temporary roots must follow the documented owner
API; raw native pointer mutation is outside the managed language proof.

`tests/managed-graphs.py` drives list/field self-cycles, mutually recursive
aliases and replacement, temporaries retained across later arguments, growing
and shared Lists, a live ring while dropping garbage, and 100,000 self-cycles.
Generated LLVM links to an exact accounting runtime: normal return must leave
no live owners after deferred debt is drained. It also compares identical
input paths against the saved foundation compiler, checking exact old LLVM for
JSON, bottom-up recursive trees and ordinary mutable records/Lists.

`tests/managed-graphs-profiles.py` runs the native independent reachability
oracle on system, fixed, lazy and eager heaps, multiple poll budgets and seeds,
at native O2 and ASan/UBSan. Small budgets interleave root/mark/sweep phases and
every owning-edge operation. Exact objects/bytes and per-poll work are checked;
the fixed/lazy test pool is one MiB. These tests are short exact-accounting
tests, not an hours-long application soak.

Recorded macOS arm64 evidence before the remote-only measurement instruction:
the quick native/sanitizer matrix passed all four
heaps with budgets 1 and 32 (eager has no bounded poll), seeds 314159 and
4294967295. Compiled graph/alias cases passed O0/O2 with exact accounting.
Existing LLVM identity and a separate untraced recursive component passed.
Independent normal-runtime C compilation against the foundation source produced
byte-identical ordinary object files. The cycle engine passes strict Windows
Clang 18 target cross-compilation; actual Windows execution is still required.

Before moving graph emitter bookkeeping into the optional frontend, the first
self-compilation run failed the wall gate: 31.45 ms versus the
unchanged 25 ms ceiling. After reducing fixup bookkeeping and running paired
controls, the original-source baseline measured wall p90 15.24 ms, CPU p90
10.36 ms, RSS 9.5 MiB and 72.24 million retired instructions. The candidate's
larger current source measured 14.90 ms, 10.37 ms, 9.6 MiB and 74.79 million.
The unchanged ceilings are 25 ms, 22 ms, 10 MiB and 75 million. The instruction
margin is narrow; these controls are absolute gate evidence, not proof that
compiler instruction counts are equal or that arbitrary cycles cost nothing.

Callback syntax is `Callback<ArgumentTypes..., ReturnType>` and
`function(parameters...)[: ReturnType] { body }`. A return-only signature such
as `Callback<Nothing>` has no parameters. Calls are statically checked. Private
environment records contain exact typed capture fields plus an execution
domain identity; callback records own their environment. Scalar captures are
snapshots and reference captures preserve object aliases. Captured bindings
cannot be rebound inside a callback; capture a record and mutate its fields
when shared local state is needed. Callback arguments and results follow the
same owned/borrowed conventions as ordinary function calls.

The ordinary parser requests the optional generated frontend with exit status
86 after recognizing typed callback or anonymous-function syntax. No source
string search selects it. The adapter extends the current core parser, module
resolver and ownership emitter instead of maintaining a separate copy.
Closure bodies have their own newline/delimiter scope inside call arguments.
Ordinary scalar-record replacement is disabled in this optional frontend:
capturing an otherwise field-only value is a hidden object escape. Final graph
analysis includes callback/environment edges before selecting traced stores.

`eventcallbacks` layers callbacks on the existing `eventloop` batch module.
Ordinary batch-loop users do not import callable types or select the extension.
`eventcallbacks.nativeLoop(dispatcher)` returns an `errors.IntegerResult` with
a borrowed native loop identity while the dispatcher is open. This lets an
AppKit observer share its wait source; callbacks still run through
`dispatch(dispatcher, 0, maxEvents)` on the owner thread. Detach platform
observers before closing the dispatcher, and do not close the borrowed loop or
change its registrations. A closed dispatcher returns a recoverable error.
Dispatch uses direct slot tokens and native registration identities to reject
stale events. Cancellation releases captures; one-shot timers retire before
calling their callback; callbacks selected into a returned batch stay alive
through their call even if cancellation or closing removes registry owners.
Before sleeping, this opt-in dispatcher services one bounded collector batch.
When debt remains it polls readiness without sleeping and may return an empty
batch, letting its caller schedule other work. Once debt drains, the requested
OS wait blocks normally. Invalid timeout contracts still return errors before
the wait; cleanup cannot turn an invalid timeout into a valid zero timeout.
The idle regression drops a 1,025-node ring with no future I/O or timers,
checks exact reclamation, then checks that a subsequent wait blocks. The
ordinary runtime and raw batch event loop contain no new collector hooks.
Creator-domain checks run before callback entry touches stack or RC state.
Process-lifetime unique domain identities prevent recycled OS thread IDs from
authorizing a stale callback. That small atomic identity allocator exists only
in the optional runtime, and does not make heaps shared.

`workers.spawnSelf(mode)` launches this executable with `--minyar-worker` and
the supplied mode. The child checks `workers.isWorker()` and reads/replies with
framed Bytes messages. Child stdout is reserved for that protocol. Parents use
`send`, `receive(timeoutMs)` and `close`; `send` success means a complete copied
frame was accepted into the bounded native queue. `receive` also pumps queued
sends. Messages are capped at 16 MiB and pending output at 32 MiB. Clean EOF,
empty successful messages, would-block, and truncated/malformed-frame failures
are distinct. Closing cancels and reaps that child; process exit cleans up
remaining children. No shell interprets the executable or mode argument.

Each process owns its own managed heap, pool, frames, caches and lazy Text
state. Concurrent managed programs are usable without changing ordinary RC.
Process startup and RSS are higher than thread costs; this is not a managed
thread implementation. A thread backend still requires execution-domain state
migration and isolated literal/lazy-index handling, rather than atomic counts
alone. The Windows backend uses stable per-worker `OVERLAPPED` state, bounded
copied frame queues, UTF-16 `CreateProcessW` arguments, an explicit inherited
handle list, and kill-on-close jobs. Registry growth never moves pending I/O
state or buffers. Its named-pipe ACL grants only the creating account, rather
than the default Everyone/Anonymous read grants described by Microsoft's
[pipe security contract](https://learn.microsoft.com/en-us/windows/win32/ipc/named-pipe-security-and-access-rights).
This separates managed heaps and channel ownership; executable workers still
have their user's normal OS permissions and are not an untrusted-code sandbox.
Parent waits block on I/O completion events; child pipe ends
remain synchronous. Startup creates the process suspended, assigns its private
job, then resumes it. Close cancels pending operations before releasing their
buffers, terminates the worker, and waits for process cleanup. These choices
follow Microsoft's [overlapped I/O](https://learn.microsoft.com/en-us/windows/win32/ipc/synchronous-and-overlapped-pipe-i-o)
and [restricted handle inheritance](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute)
contracts. Arguments use the documented [quote and backslash rules](https://learn.microsoft.com/en-us/cpp/c-language/parsing-c-command-line-arguments).

The native Windows worker fixture checks real pipe ACLs, unrelated inheritable
handle exclusion, cancellation with both a read and a write pending, malformed
coordinator-side output, chunk boundaries and exact handle release. It requires
descendants to terminate on close and on abrupt coordinator exit, including
when ordinary `atexit` cleanup is bypassed. These subprocess isolation controls
also follow the adversarial handle-lifetime approach in
[CPython's subprocess tests](https://github.com/python/cpython/blob/main/Lib/test/test_subprocess.py).

Short TDD checks cover escaping scalar/reference captures, hidden closure
cycles, indirect reference arguments/results, nested callbacks/recursion,
module record signatures, shadowing, cancellation, malformed input and every
truncated worker frame prefix. Exact allocation/debt accounting runs at O0/O2.
Generated capture boundaries exposed and drove fixes for scalar replacement
and newline parsing. Foreign callback/environment entry is rejected before
RC/frame access.

The actual portable launcher is also tested at debug/release on system, fixed,
lazy and eager profiles, including cleanup budgets 1 and 32. These cases check
the selected runtime and stack-owner ABI, callback-driven timers, a captured
cycle, nested List result types, and parsed extension fallback from the
incremental module driver. New features currently fall back to whole-program
compilation; they do not yet have incremental slice caching.

After callback dispatch was added, a local gate already in flight measured
75.31 M retired instructions and failed the unchanged 75 M ceiling. Local
measurements were then stopped following the user's remote-only instruction;
dispatch allocation was reduced but no new macOS performance claim is made.
Remote Ubuntu24.04/LLVM23 paired controls measured foundation wall/CPU p90
14.18/13.82 ms and 16.4 MiB RSS, versus candidate 14.83/14.46 ms and 16.3 MiB.
Both pass the existing time ceilings and both fail the Apple-calibrated 10 MiB
RSS ceiling. No threshold changed. The available x86 PMU measured 58.50 M and
61.12 M user instructions respectively; those are not the macOS retired
instruction metric. Remote evidence is under `build/remote-evidence`; the
candidate remains unmerged pending compatible-platform gate evidence.

The final remote validation preserves [logs and source-hashed coverage](research/evidence/managed-graphs-2026-10-10/README.md).
Compiler coverage is 79.70%, ordinary runtime lines 80.73% and branches 66.16%,
passing the unchanged 79/72/55 gates. All 18 callback cases pass native and
ASan/UBSan at O0/O2, including value names that resemble generic type syntax.
The normal O2 system runtime object is byte-identical to a separately compiled
foundation runtime archive. These are correctness/compatibility results; the
earlier paired performance files precede the final optional-frontend split.
