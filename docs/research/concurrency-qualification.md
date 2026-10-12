# Shared-memory concurrency release gates

This is a qualification plan, not passing evidence. WS1 remains held for
`PHASE1_DONE` and Boat admission. The release must include safe shared
managed values; isolated Bytes messages alone do not complete it.

The selected public synchronization primitive is a bounded channel; its
implementation uses a native mutex/condition variable. A public generic
`Mutex<T>` is not required by this decision. If one is added, its guarded
access and no-reference-escape rules need their own compiler and stress gates.

## Freeze and integration

Record the qualified, pushed `v2` base, compiler/runtime/provider hashes,
toolchains, exact commands, exit statuses and raw observations. Rebase each
small reviewed WS1 chunk onto that base. Only the integrator merges and
pushes. Record the resulting `v2` SHAs and platform suite/CI receipts before
changing the verification map or marking neo-vm VMM-2 fixed.
The cited [design decision](../concurrency-design.md) and
[neo-db executor proposal](../concurrency-neodb.md) must receive independent
review. Their source coverage must include Swift atomics/actors, Rust Rc/Arc
and Send, Python split counts, Pony, Erlang and Nim ORC. Freeze the exact
supported boundary types and operations before implementation qualification.

## Compiler and ownership regressions

Test both accepted programs and rejected programs across ordinary, module,
closure and Result frontend paths, including cold and warm incremental
builds. A rejected boundary must produce a diagnostic and no executable.
The accepted path must exercise managed data across actual OS threads.

Warm a safe multi-module caller/helper graph, then change a helper's body to
add a raw-address, unknown native or indirect unsafe effect without changing
its signature. Leave the caller unchanged. Require the warm build to reject
as the cold build does, with no new runnable output. Repeat for a
helper-of-helper edge change and closure/Result routes; an executable left
from the earlier successful build cannot count as the rejected build's output.
Either disable incremental reuse for threaded graphs or preserve resolved
call/effect summaries with schema/policy invalidation and recheck the complete
graph even when body IR is reused.

- Reject mutable Text, Bytes, Lists, Maps, nested records and callback
  captures at shared boundaries unless the dedicated ownership operation
  establishes their permitted state. An unused unsafe parameter is still
  unsafe. Scalars containing machine addresses must not bypass the rule.
- Check the resolved transitive call graph, including main/sender effects,
  qualified names, recursive helpers, native calls and indirect calls.
  Native package names and user annotations are not safety proofs.
  Include a sender that saves `machine.address(bytes)` before transfer, hides
  it in scalar/record/List storage, or passes it to a native retainer. A checked
  threaded executable must reject these escapes on both cold and warm paths.
- Reject use after exclusive transfer through aliases, fields, branches,
  loops and returned values. If the Bytes stage detaches a buffer and leaves
  all sender aliases empty instead, verify that exact documented behavior;
  do not present it as general affine graph transfer.
- Verify simultaneous reads of the same FrozenBytes backing, creator exit
  before the readers finish, and exact final-drop reclamation. Ordinary Text
  and Bytes remain local and are rejected at direct sharing boundaries.
  Concurrent first use of the same Unicode literal must obtain local headers
  and local lazy indexes/cursors. Test local slice/backing lifetimes; no
  mutable header or retained private pointer may escape its domain. Mutation
  through FrozenBytes must fail at compile time. If FrozenText is later
  admitted, preindexing alone must not leave a shared writable cursor.
  Threaded literal copies must own valid allocator-prefixed storage; test
  concatenation/growth, slices and teardown so static backing is never freed
  or reallocated through the ordinary owning-Text path.
- For every zero-copy path, compare the backing allocation addresses and
  contents before/after publication. Exercise empty buffers, spare capacity,
  repeated transfers and sender mutation after transfer. Count allocations
  and payload copies; elapsed time alone does not prove zero-copy behavior.
- Failed spawn/send and timeout/full/closed channels preserve documented
  ownership. Queue limits count both messages and retained allocation bytes.
  Exercise allocation failure before and after preparing the launch packet.

## Runtime, collectors and synchronization

Run actual generated-language programs and C stress fixtures. Every worker
creates and releases Text, Bytes, Lists, records and local cycles while other
workers do the same. Verify distinct frame stacks, collector registries,
proof/phase state, caches, stack bounds and recovery state. At joined exit,
drain deferred debt and release caches; exact allocation accounting and leak
checks must cover each domain as well as the process total.

Coordinate entry and exit emission with WS2 G14. Its read-only audit found
that stack-owner eligibility consults `state[5]` while indirect callbacks
update `state[14]`, and `finishStackOwnership` assumes the preceding output
slot is a definition tail although closure emission puts domain validation
there. Require a Bytes-owning callback wrapper with an indirect nonleaf call,
preserved callback-domain validation and exact paired stack-frame leaves.
Threaded entry/exit and recovery must use structured entry metadata; a generic
bounded leave must never enqueue a stack-backed ownership frame. These are
unexecuted regressions, not evidence that either emitter has been repaired.

Shared control blocks and immutable backing stores need balanced atomic
lifetimes for wrappers, queued packets, running threads and blocked
operations. Exercise retain/release contention, last drop by another thread,
close versus send/receive, multiple joins, self-join, dropped handles,
bounded-queue backpressure and wakeups. A handle must not be freed while an
operation is using it. Reject unsupported pool/arena configurations explicitly.
Inspect generated IR/runtime objects or targeted ownership counters to prove
that local managed retain/release still uses non-atomic counts **inside a
threaded artifact**, while shared backing/control lifetimes follow the atomic
protocol. Ordinary artifact identity alone does not prove that split.

Exercise the channel's native mutex with a mutual-exclusion oracle and
publication/visibility checks, contention, blocked waiters, close/drop races
and exact safe destruction. Include generated-language channel operations in
TSan stress. If a public mutex is added, also reject escaping a protected
managed borrow outside its guard and test its separate lifetime contract.

Demonstrate that a worker can block in a real kernel operation while another
worker progresses and the main thread remains responsive. VMM-2 qualification
must use the hosted thread API and the reviewed syscall path, coordinated
with WS2 VMM-1; do not credit process workers or a C pthread shim as a language
thread result. Linux, macOS and Windows focused native/provider checks and the
integrator's complete suites remain separate evidence.

## ThreadSanitizer

On an admitted Linux Boat host, build the runtime, native concurrency code
and generated-language code with ThreadSanitizer instrumentation. Inspect
the linked binary and emitted IR for actual TSan accesses/callbacks; linking
the sanitizer runtime alone is insufficient. Retain compiler flags, runtime
identity, host architecture and source hashes. Use `halt_on_error=1`, retain
stderr, and require zero race reports and successful test oracles. Do not add
suppressions or disable instrumentation to make a stress case pass.

Stress the concurrent lifetime/close/join cases, domain-local collectors,
Unicode literal caches and real kernel blocking. Also run ASan/UBSan and
Linux leak checks separately; TSan is not a replacement for those checks.
Diagnose unsupported sanitizer hosts as an infrastructure failure, never as
a clean stress result.

## Single-thread ±1% gate

Compare the qualified base and candidate on the same quiet admitted host,
with identical inputs, memory profiles, optimization, toolchain and affinity.
Cover compiler self-compilation, Minyarcraft, Atacama, JSON workloads and
neo-db statement microbenchmarks specified by the shared brief. Preserve
existing benchmark limits and correctness outputs.

Warm both artifacts, then collect paired interleaved observations with a
predeclared sample count (at least 30). Record raw samples, central timing
ratios and uncertainty. To establish the requested unchanged behavior, the
candidate/base timing ratio must be within `[0.99, 1.01]`; noisy observations
whose predeclared uncertainty interval is not contained within that band
remain unqualified. Do not
substitute the existing looser performance tolerance. Byte-identical ordinary
runtime objects and emitted LLVM strengthen the conclusion but do not replace
the requested application measurements.

## Eight-vCPU scaling gate

Use an admitted Boat sandbox with eight available vCPUs. Record CPU topology,
affinity, cgroup quota, load, toolchain and source hashes. Measure a fixed total
workload at 1, 2, 4 and 8 threads; verify the same result at every width and
include launch/join and shared input publication in the timed region. The
parallel workload must exercise the shipped shared managed-value API rather
than the old scalar-only ABI.

Proposed conservative interpretation of near-linear: median speedup at eight
threads at least `7.2x` (90% efficiency), with a 95% interval whose lower bound
is at least `6.4x`. Freeze this interpretation with the integrator before the
run; never revise it after seeing results. Choose the workload size before
measurement so it dominates launch overhead, retain paired raw samples and
show the complete scaling curve. Also retain channel/transfer throughput as
a separate measurement. A hand-selected best run does not qualify the gate.
