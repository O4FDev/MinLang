# Ownership, callbacks, cycles and recoverable errors

Research and implementation record, 2026-10-10. This distinguishes the working
error-value module from language/runtime work that has not been implemented.
Upstream documentation and sampled official test sources were inspected; no
upstream suite was executed and no claim of a community consensus is made.

## Decision

Keep ordinary managed values confined to one execution domain. Keep the
existing eight-byte ownership prefix and non-atomic reference-count operations
for that domain. Run network callbacks on the event loop that owns their data.
Use isolated workers with explicit message transfer for managed parallelism;
begin with copying messages at the boundary. Atomic counts alone cannot make
the present runtime thread-safe. Shared immutable buffers, if needed, require
a separate representation and synchronization protocol.

Use explicit typed result values for recoverable failures. The implemented
`library/errors.min` provides concrete `IntegerResult`, `BooleanResult` and
`BytesResult` records on today's compiler. Adopt tagged `Result<T, E>` and
exhaustive matching before adding propagation sugar such as `?`. An OS read
failure or invalid packet becomes a result; invalid indexing, integer overflow,
violated runtime invariants and explicit `fail` remain fatal. There is no
unwinding exception implementation in this work.

Do not merge the cycle branch on a claim that existing single-threaded programs
are unchanged in cost. It has useful implementation and regression coverage,
but its measurements show overhead on recursive types used acyclically. Its
collector needs extensions for closure environments and an ownership-domain
boundary before managed threads are permitted.

## Current implementation constraints

`docs/runtime-memory.md` proves acyclicity by excluding reference mutations
whose static type graph can return to the receiver. It explicitly excludes
closures and foreign pointers from that proof. Captured reference values add
heap edges that the current record/List graph does not represent.

The current runtime has more shared mutable state than its reference counts:

- `runtime/minyar_rc.h`: ownership frames, frame caches, pending work and test
  ledgers are file-static globals.
- `runtime/minyar_bounded_rc.h`: object/frame/chunk retirement queues and their
  cursors are global; queued objects retain owning references until visited.
- `runtime/minyar_pool.h` and `runtime/minyar_heap.h`: pool allocation and
  accounting are not a synchronized shared allocator.
- `runtime/minyar_runtime.c`: stack depth/bounds, compiler arenas, integer and
  character Text caches are shared state. Text's lazy Unicode index and its
  recent-position cursor mutate even though its visible characters are
  immutable. Merely sending an immutable-looking Text pointer is unsafe.
- The original `runtime/native/net.c` has a single `last_error` buffer; its
  `receive` returns empty Bytes for both EOF and `recv` failure. A stale error
  string cannot recover that lost outcome information.

`finishParallelFunction`, `parallelRuntimeAllowed` and `checkParallelCalls` in
`compiler/compiler.min` deliberately allow only scalar parameters/locals/results
and other scalar-safe parallel functions or intrinsics. Keep this restriction
until the managed execution-domain implementation and checks exist. Ordinary
functions, captured environments and result records must not be passed to this
existing parallel ABI.

## What peer runtimes actually provide

| System | Inspected mechanism | Useful Minyar lesson |
| --- | --- | --- |
| Swift | ARC has atomic machinery and optimized non-atomic operations; actors isolate mutable state and sendability checks constrain boundary transfers. Actors do not make a multi-step operation atomic across suspension points. | Protect mutation as well as lifetime; pin UI/network state to its domain. Do not infer race freedom from atomic retain/release. [Concurrency](https://docs.swift.org/latest/documentation/the-swift-programming-language/concurrency/), [runtime counts](https://github.com/swiftlang/swift/blob/488fdfe4523bb35326ca384fda4c00e1e5581301/stdlib/public/SwiftShims/swift/shims/RefCount.h). |
| Rust | `Rc` is non-atomic and cannot be sent between threads. `Arc` uses atomic counts, but its payload still needs suitable `Send`/`Sync` behavior; mutation commonly needs synchronization. Strong cycles are not automatically collected. | Preserve a distinct local fast path; make cross-domain access a checked operation. [Rc](https://doc.rust-lang.org/std/rc/), [Arc](https://doc.rust-lang.org/std/sync/struct.Arc.html). |
| Python free-threading | PEP 703 combines owner-local and atomic shared counts, deferred counts, synchronization for containers, thread state and cycle-collection coordination. An owner check is part of the proposed biased-count fast path. | This solves compatibility with Python's shared dynamic object model; adopting only split counts would leave Minyar's queues, caches, fields and collector unsafe. It also adds a local owner check/header cost. [PEP 703](https://peps.python.org/pep-0703/). |
| Pony | `iso` can transfer mutable ownership; `val` allows immutable sharing; ordinary mutable references cannot be sent. Intra-actor object collection and inter-actor collection are distinct protocols. | Domain isolation reduces synchronization requirements. A complete capability lattice and concurrent actor-cycle protocol are substantial new language/runtime complexity. [Reference transfer](https://tutorial.ponylang.io/reference-capabilities/passing-and-sharing), [GC](https://tutorial.ponylang.io/runtime-basics/garbage-collection.html). |
| Erlang | Processes isolate their heaps. Message transfer copies most terms, with special handling for reference-counted binaries. | Copying messages is a coherent initial boundary even if zero-copy transfer later becomes useful. Do not promise constant-time copies of arbitrary graphs. [Process messages](https://www.erlang.org/docs/17/efficiency_guide/processes.html). The linked historical guide supplies the copying model, not current process memory estimates. |
| Nim ORC | ORC adds cycle collection to ARC; type analysis can remove cycle machinery for acyclic types. Nim's memory-management documentation explicitly does not make ordinary managed references safe across threads. | Reuse type-selective collector lowering, while treating concurrency as an additional problem. [Memory management](https://nim-lang.github.io/Nim/mm.html), [ORC rationale](https://nim-lang.org/blog/2020/12/08/introducing-orc.html), [implementation](https://github.com/nim-lang/Nim/blob/b081880000a4d708cdce6afcc4c4124a60a5c62e/lib/system/orc.nim). |

These are different guarantees, not interchangeable implementation recipes.
The recommendation above is an inference from those mechanisms and Minyar's
existing global state and performance contract.

## Audit of `port/astra-cycles-v2`

Inspected read-only at commit `976a75a` in the existing
`/Users/luke/Projects/Minyar-Lang-astra-v2` worktree. No cherry-pick, merge,
checkout change or modification to that worktree was performed. Compared with
v2, it adds `runtime/minyar_cycles.h`, `runtime/minyar_cycles_collect.h`, traced
collection/ownership entry points, compiler type reachability lowering,
runtime graph-model tests, source fixtures and profile matrices.

Its collector is a single-threaded snapshot tracer beside authoritative RC:

1. Potentially cyclic record/List types receive 32 additional bytes before the
   ordinary ownership header. Other types keep the original layout.
2. Incoming counts track traced owning aggregate slots. Ordinary count minus
   incoming count identifies external owners, including locals, temporaries,
   native owners and deferred retirement slots; collector pins are accounted.
3. A captured finite cohort passes through roots, mark and sweep phases.
   Barriers shade roots/edges when references are removed, replaced or
   transferred during collection. New allocations cannot extend that cohort.
4. The scheduler meters root/field/phase work with the existing cleanup budget.
   This is a work-unit guarantee, not a wall-clock pause or fixed-heap capacity
   guarantee. No collector thread is present.

The useful tests include self-cycles, growing Lists during epochs, live rings
beside garbage churn, a temporary-only root during an actual collection,
ownership transfers that create garbage without a count decrement, and an
independent reachability oracle under changing roots and edges. In-place
`x = x.appended(e)` has an additional regression because reusing v2's untraced
append without recording its edge leaked cycles. The branch records a red
commit and mutation evidence for that case. These are valuable TDD inputs.

Its own final measurements against v2 at `a836412` report:

| Existing workload | Retired-instruction change | Memory observation |
| --- | --- | --- |
| JSON history parsing | +6% to +9% | Reported footprint increases |
| Constructor-only recursive chain | +12.8% | 1.97 to 2.29 MB RSS |
| 100,000-record chain | +15.3% | 12.6 to 19.1 MB RSS |
| Compiler arena/craft consumer | Within reported noise | Not evidence of zero cost for recursive application values |

Source: that branch's `research/cycles/README.md` and
`research/cycles/validation.md`. These are recorded historical branch results,
not fresh measurements on today's v2. The validation document explicitly
records a failed unchanged absolute self-compile budget, including an
independently failing baseline; it is not evidence of a fully green gate.

The branch still charges recursive types that never form cycles: metadata,
registry operations and incoming counts begin before tracing becomes active.
After activation, collecting a cohort can visit unrelated live objects. These
costs must be measured against the real JSON, compiler and Tolum consumers.
An opt-in feature/profile is a possible compatibility boundary, but it does
not satisfy a claim that enabling arbitrary cycles costs nothing.

## Closures and managed threads as one design

The following is a proposed implementation sequence, not implemented syntax.

Start with typed callbacks of fixed signatures and captures by value. A
non-escaping callback may use a proven stack environment; an escaping callback
owns a managed environment containing a code pointer and typed capture slots.
Capturing a mutable List or record preserves its existing shared-reference
semantics within the domain. Capturing a scalar by value snapshots it. Mutable
captured bindings need explicit boxed storage if subsequently supported; never
quietly capture pointers to dead stack slots.

The environment is an aggregate with an exact reference map. A cycle can be
`record -> callback -> captured record`, even when the callback's public
function signature says nothing about that captured type. Extend reachability
analysis to hidden environments and conservatively trace escaping callbacks
with managed captures when their possible storage closes a cycle. Treating
only the function's parameter and return types as edges is unsound. The cycle
registry, incoming counts and every relevant transfer/mutation barrier must
understand environment slots; if boxes exist, they need the same treatment.

Callback registration owns the callback. Dispatch takes a temporary owner
before invoking it so the callback can cancel/deregister itself. Cancellation
detaches registration exactly once, and does not free the environment while
dispatch is executing. A stale native handle must not call a new registration
that happens to reuse its slot; use a generation. Native callback execution
enters the owning event loop, never the thread that happened to signal I/O.

For managed worker domains, compile a distinct runtime configuration with
domain-local/TLS frames, queues, collector registry, allocator state and
caches. The normal single-domain build retains ordinary globals and its
existing entry points, avoiding a TLS fetch or owner-tag branch on each retain.
This separation itself does not prove a performance pass: inspect generated
IR/machine code and rerun all unchanged resource ceilings.

Initial messages contain checked scalar values and copied Text/Bytes or
serialized typed records. Deserialization allocates local managed values.
Reject local Lists, records, callbacks and result records crossing into another
domain by raw pointer. A future graph-copy operation needs an identity map to
preserve aliases/cycles and bounds on total bytes/depth; retry/OOM behavior must
be specified. A worker owns its reactor/connections, and message channels have
bounded queues and cancellation. Actor-per-connection is not required:
many cheap connection states can share a few domain reactors.

If copying becomes a measured bottleneck, add explicit frozen byte buffers
with their own atomic lifetime header; allocate them independently of an
actor's local pool. They must be transitively immutable and have no lazy
unsynchronized index/cursor. Restrict cross-domain owning cycles initially:
actor handles must not keep ordinary local graph pointers in another domain.
Collecting distributed actor-handle cycles requires an additional protocol,
not the Astra collector or a single atomic decrement.

## Error design comparison

There is no primary-source evidence here that establishes one design as the
universally best or least buggy. Select by explicit handling, composability,
cleanup safety and Minyar's implementation/ABI costs.

| Design | Useful property | Minyar consequence |
| --- | --- | --- |
| Rust `Result` with `?` | Expected failures have a typed success/error branch; discarded results are linted, and `?` returns early. | Best eventual fit with exhaustive variants and existing scope cleanup. Do not add `?` before result typing and ownership lowering. [Result](https://doc.rust-lang.org/std/result/). |
| Swift typed `throws` | A declared thrown type can preserve errors through function/closure signatures. | Requires effect checking and throwing-function ABI/lowering. Swift's own proposal does not recommend typed throws as the universal default. [SE-0413](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0413-typed-throws.md). |
| Zig error unions | Error sets pair with success payloads; `try`, `catch` and error-only cleanup compose. | A tagged union and propagation are useful; copying Zig's allocator/manual-cleanup semantics would conflict with Minyar ownership. [Reference](https://ziglang.org/documentation/master/#Error-Union-Type). |
| Go errors as values | Ordinary values and straightforward local branches support reusable error-processing functions. | Useful immediate model. Sentinel/empty payload plus a separate global error loses information; keep the error in the operation result. [Official discussion](https://go.dev/blog/errors-are-values). |
| Gleam/OCaml results and matching | Explicit variants compose; pattern exhaustiveness can catch omitted cases. | Adopt the variants/exhaustiveness contract, not foreign syntax or VM assumptions. [Gleam result tests](https://github.com/gleam-lang/stdlib/blob/13359e53d6256c4f1ccf1a60e62dbfa3f1de2d57/test/gleam/result_test.gleam), [OCaml result tests](https://github.com/ocaml/ocaml/blob/6471927db51e6e153fcb591b1ade057f4ac9381a/testsuite/tests/lib-result/test.ml), [OCaml patterns](https://ocaml.org/manual/5.4/patterns.html). |

## Working error-value API

`library/errors.min` is implemented using public record types with private
fields, preventing external construction/mutation of result tags. A positive
classification code identifies a recoverable error; `nativeCode` preserves the
OS diagnostic independently. Unknown positive codes remain failures rather
than being mistaken for success. Messages are owned Text values and remain
valid after subsequent operations.

```minyar
use "errors" as errors

function parse(packet: Bytes): errors.IntegerResult {
    if packet.length < 2 {
        return errors.integerFailure(
            errors.make(errors.invalidDataCode(), 0, "short packet"))
    }
    return errors.integer(packet[0] * 256 + packet[1])
}

let result = parse(Bytes(1))
if errors.integerOk(result) {
    print(errors.integerValue(result))
} else {
    print(errors.message(errors.integerError(result)))
}
print("the program can continue")
```

The module exports factories and accessors for Integer/Boolean results and
read results. Accessing the value of a failed scalar result is a programmer
error and stops the program. Read statuses are stable:

| Status | Value | Factory | Meaning |
| --- | --- | --- | --- |
| SUCCESS | 0 | `bytes(payload)` | Received data; an empty UDP datagram is valid data |
| WOULD_BLOCK | 1 | `wouldBlock(nativeCode)` | Wait for readiness, without treating empty bytes as EOF |
| END_OF_STREAM | 2 | `endOfStream()` | Clean TCP EOF, with no error |
| FAILURE | 3 | `bytesFailure(error)` | Recoverable failure with classification/native code/message |
| TRUNCATED | 4 | `truncated(prefix, nativeCode)` | Readable datagram prefix; incomplete packet must not be silently accepted |

`bytesOk` accepts SUCCESS and END_OF_STREAM. `bytesValue` also permits a
TRUNCATED prefix, but callers must inspect status before parsing it as a
complete datagram. WOULD_BLOCK and FAILURE have no readable payload.

These are managed records, with real allocation/ownership costs, not zero-cost
sum types. Private fields ensure representation consistency, but this compiler
does not enforce handling every result, exhaustive branching or linear use.
Bytes retain ordinary alias/mutation behavior; a result's payload is not a
frozen cross-thread buffer. No callbacks, generic Result, `?`, typed throws,
managed worker domains or cycle collection are implemented by this module.

For native networking, a result must own its status/error snapshot. A native
`receivePacket` returning a packed Bytes envelope `{status, nativeCode,
payloadLength, payload}` is compatible with today's native ABI and avoids a
mutable global error side channel. Validate the envelope's lengths/statuses
before constructing `errors.BytesResult`; separate UDP sender/truncation fields
may require an expanded envelope. An operation-owned native handle can also
work, but adds a registry lifetime and leak/reuse obligations. Thread-local
last-status captured immediately by a synchronous wrapper is a transitional
implementation only; do not reuse it across asynchronous suspension or nested
native callbacks. Partial sends need a result that preserves progress even on
failure; `IntegerResult`'s failed scalar extractor does not express that.

## Compiler implementation map for the next stages

| Area | Existing functions/files to extend | Required change |
| --- | --- | --- |
| Type representation | `isReferenceType`, `llvmType`, type readers and declaration tables in `compiler/compiler.min` | Represent callback signatures and sum types explicitly; current arithmetic type IDs must not be extended by accidental range overlap. |
| Callback expressions/calls | `parsePrimary`, `parseAtom`, `parseCall`, `emitCall`, `compileFunctions` | Resolve lexical captures and generate environment/code functions; indirect call checks exact signature and domain. |
| Ownership | `ownResult`, `takeResult`, `assignReference`, `compileAtomicStatement`, runtime RC/collections | Capture ownership once, protect receiver/captures across evaluating later arguments, destroy only initialized active reference slots. Stack environments require a proved no-escape path. |
| Cyclic types | Current `checkListMutation`/`checkFieldMutation`; branch `typeMayCycle`, traced operations and cycle files | Include hidden capture/box edges and container storage, plus every add/replace/take/drop barrier. Preserve non-cyclic code generation where proved safe. |
| Domain safety | `finishParallelFunction`, `checkParallelCalls`, module declaration/interface summaries | Add checked domain/send rules rather than permitting managed references under the scalar parallel ABI. Signatures and caches include sendability/capture/effect identity. |
| Error variants/matching | Expression/statement parser, record field maps, module summaries | Represent exactly one active payload; reject accessing the wrong branch and omitted variants in exhaustive match. Do not retain/release inactive scalar bits as pointers. |
| Propagation | `parsePrimary`/`parseExpression`, `compileAtomicStatement` return lowering | Evaluate once; on Err transfer the error owner before normal local/temporary cleanup and return. A direct LLVM branch bypassing `minyar_rc_leave` leaks owners. Avoid `longjmp` and implicit catch-all panic conversion. |

## Test strategy, provenance and validation

Use independent semantic and ownership oracles plus hostile inputs, not only
factory tests. New tests in `tests/errors-values.py` were written first; the
first native test failed because `errors.min` did not exist. Adding the module
then made all eight tests pass at O0/O2. The same eight tests passed using the
sanitized compiler and runtime with ASan/UBSan and both optimization levels.
Sanitizer leak detection was disabled consistently with the repository's
ownership test configuration; that does not by itself establish no leaks.
The loop test checks retained values across 10,000 recoveries, not a measured
flat-RSS or hours-long soak claim.

Coverage includes a malformed packet error followed by a successful packet;
zero/false success payloads; EOF/would-block/failure/truncation; binary bytes;
old errors surviving later failures; combinations of error/native codes,
including unknown positive codes and signed maximum; repeated construction and
recovery; fatal invalid factory/extractor calls; and rejected private tag
forgery. No thresholds were altered and no paid infrastructure was used.

The following sampled upstream cases informed independently written scenarios.
No code, fixture contents or harnesses were copied. Sources are pinned; hashes
identify the inspected raw file. Full upstream language/GC semantics are not
asserted for Minyar.

| Official source | Revision / SHA-256 | Adaptation |
| --- | --- | --- |
| [Rust result tests](https://github.com/rust-lang/rust/blob/34f4a807e2d84184fff4e42d4539092569b6fcd6/library/coretests/tests/result.rs) | `34f4a807e2d84184fff4e42d4539092569b6fcd6`; `396549d96bac5b9752d507c470ded25e0d99fcdafbd98bb7542490be00cf0b2a` | Distinct success/error payloads and checked extraction; propagation/lazy combinator tests wait for language support. |
| [Zig error behavior](https://github.com/ziglang/zig/blob/738d2be9d6b6ef3ff3559130c05159ef53336224/test/behavior/error.zig) | `738d2be9d6b6ef3ff3559130c05159ef53336224`; `74e76e89de944e6de7dc5084e865175dac3f7cd34e631d23cd0c89edb7071f2e` | Error/payload wrapping and invalid extraction boundaries, adapted to Minyar's explicit fatal contract. |
| [Gleam result tests](https://github.com/gleam-lang/stdlib/blob/13359e53d6256c4f1ccf1a60e62dbfa3f1de2d57/test/gleam/result_test.gleam) | `13359e53d6256c4f1ccf1a60e62dbfa3f1de2d57`; `64e642856207e3dbd6b9033d8f8d217ab2575fbdba5d062ac06ab406798ee50c` | Enumerate both outcome branches and recovery; do not claim missing map/try/flatten closure APIs. |
| [OCaml result tests](https://github.com/ocaml/ocaml/blob/6471927db51e6e153fcb591b1ade057f4ac9381a/testsuite/tests/lib-result/test.ml) | `6471927db51e6e153fcb591b1ade057f4ac9381a`; `440e1d0e29c004acfaf0f5b7b976b42e9ef374cf3e2a1951d5d84e77e6509f11` | Predicate/value/error cases; [exhaustiveness fixtures](https://github.com/ocaml/ocaml/blob/6471927db51e6e153fcb591b1ade057f4ac9381a/testsuite/tests/typing-warnings/exhaustiveness.ml) inform a future compiler rejection matrix. |
| [Swift typed throws diagnostics](https://github.com/swiftlang/swift/blob/488fdfe4523bb35326ca384fda4c00e1e5581301/test/decl/func/typed_throws.swift) | `488fdfe4523bb35326ca384fda4c00e1e5581301`; `80b91b0caaf67c9cc8725a465c73a9b12294df9128ed0625ed7435c71144ce2e` | Future reject invalid error/callback conversions, paired with successful native cases. |
| [Swift transferred closure captures](https://github.com/swiftlang/swift/blob/488fdfe4523bb35326ca384fda4c00e1e5581301/test/Concurrency/transfernonsendable_closure_captures.swift) | Same Swift revision; `8cb5b9d90a9b1eefba9d75e049942f5c20d3f003ced0885c2a42565570bed84f` | Future reject crossing then reusing mutable aliases, including nested captures and callbacks, not just direct arguments. |
| [CPython free-threaded GC](https://github.com/python/cpython/blob/9d22a5334bd5273962adceeb697a1337e9a0ca21/Lib/test/test_free_threading/test_gc.py) | `9d22a5334bd5273962adceeb697a1337e9a0ca21`; `bc160ebc5c9983ff041a2c6788416742f3994ae8936fcd5aa50069b0be2a2846` | Future barrier-synchronized mutator/collector scenarios and detached-thread lifetime tests; these cannot run under today's local managed model. |
| [Nim self-cycles](https://github.com/nim-lang/Nim/blob/b081880000a4d708cdce6afcc4c4124a60a5c62e/tests/arc/torc_selfcycles.nim), [graph cycles](https://github.com/nim-lang/Nim/blob/b081880000a4d708cdce6afcc4c4124a60a5c62e/tests/arc/torc_basic_test.nim) | `b081880000a4d708cdce6afcc4c4124a60a5c62e`; self `08ec74c6b4766099739b2ced3c29b0764011552453e70deeb64857985e4043cf`, graph `d5ea4288873a2c9383452a62741412f47730443a627e560d95c3a833b59520e9` | Existing Astra self/ring/graph oracles are the immediate Minyar analogue. Add callback environments before claiming closure-cycle coverage. |
| [Pony dynamic trace fixture](https://github.com/ponylang/ponyc/blob/5dfaedf8dbe27a35ec8c4e49ba117d3278200579/test/full-program-tests/codegen-trace-iso-to-val-through-dynamic-tuple/main.pony) | `5dfaedf8dbe27a35ec8c4e49ba117d3278200579`; `ab06f4f66fa02390864a1abf037dcee4784564ac256e3c5a4de0655c7807d771` | Future trace hidden aggregate/reference paths; a direct-field-only ownership test misses them. |
| [Erlang GC suite](https://github.com/erlang/otp/blob/516126e9209377f003a4bcaa9822cdcb139f9a13/erts/emulator/test/gc_SUITE.erl) | `516126e9209377f003a4bcaa9822cdcb139f9a13`; `e52a3e5718fb3cfe08290530b3b8f39f4e6cede6ad9a2cd1dedf5bce05702544` | Future stress local heaps/mailboxes under growth and blocked delivery; do not copy VM heap-size expectations. |

Repository license sources were checked: Rust [MIT](https://github.com/rust-lang/rust/blob/34f4a807e2d84184fff4e42d4539092569b6fcd6/LICENSE-MIT) (also Apache-2.0), Zig [MIT](https://github.com/ziglang/zig/blob/738d2be9d6b6ef3ff3559130c05159ef53336224/LICENSE), Swift [Apache-2.0 with runtime exception](https://github.com/swiftlang/swift/blob/488fdfe4523bb35326ca384fda4c00e1e5581301/LICENSE.txt), Gleam [Apache-2.0](https://github.com/gleam-lang/stdlib/blob/13359e53d6256c4f1ccf1a60e62dbfa3f1de2d57/LICENCE), Nim [MIT](https://github.com/nim-lang/Nim/blob/b081880000a4d708cdce6afcc4c4124a60a5c62e/copying.txt), Pony [BSD-2-Clause](https://github.com/ponylang/ponyc/blob/5dfaedf8dbe27a35ec8c4e49ba117d3278200579/LICENSE), Erlang [Apache-2.0](https://github.com/erlang/otp/blob/516126e9209377f003a4bcaa9822cdcb139f9a13/LICENSE.txt), and OCaml [LGPL-2.1 with linking exception](https://github.com/ocaml/ocaml/blob/6471927db51e6e153fcb591b1ade057f4ac9381a/LICENSE). CPython's [license](https://github.com/python/cpython/blob/9d22a5334bd5273962adceeb697a1337e9a0ca21/LICENSE) includes PSF and historical terms. This is a provenance record, not authorization to copy all files: copied code would require applicable file notices, attribution and an individual-file audit.

Required future tests include compile-fail domain violations; captured values
escaping/reentering/cancelling; cyclic callbacks stored inside captured records;
every root/edge/take transfer while the collector is in each phase; exact live
object/debt accounting after drains; deterministic seeded reachability graphs;
TSan on supported managed-concurrent configurations; scheduler progress and
bounded mailbox rejection; propagation from nested expressions with aliases;
allocation-failure injection; all packet prefix truncations and huge lengths;
OS error/status snapshots surviving another operation; and shutdown with
pending callbacks, partial sends and worker messages. Original failures remain
failures after diagnostic reruns. Native execution, ownership oracles and
sanitizers complement each other; no one of them is a substitute for the others.
