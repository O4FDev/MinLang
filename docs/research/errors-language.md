# Typed recoverable errors: implemented optional language frontend

This implements a small checked error-value language in an optional native
Minyar frontend. It does not change `compiler/compiler.min`, the ordinary
runtime, the ordinary compiler build, or any global resource/coverage gate.
Build/catalogue/launcher integration belongs to the CI task; this branch
provides only the dedicated compiler extension, module, tests and documentation.

## Language contract

```minyar
function parse(packet: Bytes): Result<Integer, Text> {
    if packet.length < 2 { return Err<Integer, Text>("short packet") }
    return Ok<Integer, Text>(packet[0] * 256 + packet[1])
}

function describe(packet: Bytes): Result<Text, Text> {
    let number = try parse(packet)
    return Ok<Text, Text>(Text(number))
}

match describe(Bytes(1)) {
    Ok(value) { print(value) }
    Err(error) { print(error) }
}
```

* `Result<T,E>` is a distinct static type for each pair of payload types.
  Payloads may be scalar, Text, Bytes, records, Lists, callbacks or nested
  Results. It is special-purpose type instantiation, not generic functions.
* Constructors spell both types explicitly: `Ok<T,E>(value)` and
  `Err<T,E>(error)`. The compiler verifies the active payload against its type.
  A zero, false or empty payload is a success when tagged Ok.
* `match expression { Ok(binding) { ... } Err(binding) { ... } }` evaluates
  the expression once, requires exactly both arms in either order, rejects
  duplicates/unknown arms, and scopes each binding to its arm. Both returning
  arms count as a complete function return. This checks outcome exhaustiveness,
  not every classification code within a user-defined error payload.
* `let value = try expression` (also with a binding type annotation) is
  propagation in a Result-returning function or callback. On Ok it binds T.
  On Err it returns `Err<U,E>` from the enclosing `Result<U,E>` function.
  E must be exactly the same static type; no implicit conversion/erasure occurs.
  The input is evaluated once and subsequent statements do not run on failure.
* This initial propagation form is restricted to a whole binding initializer.
  There is no postfix `?`, expression-level match, general pattern grammar,
  general enum declaration, error-set subtyping, unwinding or `throws` effect.
* Result tag/payload fields are inaccessible through ordinary field syntax.
  The generated representation namespace is reserved even after module
  qualification. Standalone Result expression statements are rejected.
  An unused binding is permitted, as for ordinary Minyar values; this is not
  whole-program must-use dataflow analysis.
* Bounds errors, arithmetic/runtime invariant violations and explicit `fail`
  retain their fatal behavior. Result handling cannot catch them.
* The existing scalar-only parallel ABI still excludes these managed records.
  Isolated worker transfer must encode/copy an error rather than share its
  Result pointer. This extension adds no worker transport or cancellation ABI.

Use the opt-in `build/minyarc-errors SOURCE OUTPUT --library library`
frontend. The ordinary frontend continues to reject this new syntax.
`compiler/build-errors-compiler.py` applies guarded single-match adapters
to the maintained closure/core assembler, adds native Minyar helpers and
fails closed when an anchor changes. The extension self-hosts; Python is only
the existing style of build-time assembler, not a source interpreter or
unchecked textual application-language transpiler.

## Ownership and costs

A Result is an ordinary owned three-slot record: Boolean tag, T slot, E slot.
The runtime zeros all slots/reference flags at allocation. Only the active
payload is initialized and registered as an owning reference; the inactive
reference slot stays null with its ownership flag clear. No placeholder T/E
value or default-constructor requirement is introduced. This is a tagged
representation, without a compact-union or niche-optimization claim.

Constructors use the maintained ownership transfer tokens and native record
setters. The shared primary-expression path registers the constructor's
temporary exactly once. Match pins its scrutinee in a hidden owning local
before running either arm and gives the selected binding a scope owner.
A branch may mutate/remove the original container without invalidating the
bound payload. An escaping callback captures that payload with an owner.

Propagation pins borrowed inputs, constructs an owning Err result before
leaving, and uses the exact separate rc-leave and stack-leave instruction
pieces that the existing stack-owner/leaf optimizations rewrite. Consequently
ordinary frame exit cleans parameters, locals, temporaries and enclosing
scopes on early error returns. Success binds an owner before temporary cleanup.
No runtime exception unwinder or defer stack is added.

The optional frontend includes the existing callback/graph extension. Result
constructors and reference stores participate in the same graph fixups, so
cycles through either T or E (including hidden callback environments) receive
the opt-in traced allocation and edge barriers. Acyclic ordinary application IR
is byte-identical in the identity regression. Result-using programs pay for
their records and ownership; enabling the frontend is not claimed to make
Result allocations free.

## Networking adapter

`library/results.min` converts the existing concrete status ABI to checked
generic Results and exposes typed `read`, `receiveDatagram`, `write`,
`connectStart` and `connectFinish` wrappers. It leaves `net` and `errors`
sources/ABI unchanged, so networking maintained by other tasks can adopt it
without replacing its native wire format.

A successful read carries a `Read` with owned Bytes and an explicit EOF flag.
An empty datagram remains successful data distinct from stream EOF.
A `ReadFailure` carries the operation-owned `errors.Error` and readable
truncation prefix. Would-block, system failure and truncated packets all use
Err; their classifications and native codes remain distinguishable. Truncated
prefixes cannot accidentally pass as a complete successful packet. Error and
prefix accessors are typed record APIs; the Result itself must still be matched
or propagated.

## Primary-source adaptations

All scenarios are original Minyar tests; no peer-language suite is represented
as executed. Official upstream test files were downloaded, inspected and
hashed on the Boat. Fixed revisions, paths, byte counts, URLs and SHA256s are
in [errors-peer-sources.json](errors-peer-sources.json); the retained originals
are under `/home/user/minyar-overnight/errors/primary`.

| Peer evidence | Adapted checks and deliberate limits |
| --- | --- |
| [Rust Result documentation](https://doc.rust-lang.org/std/result/) and coretests `test_try`, `test_and_then`, `test_collect` | Both outcomes, first-error short circuit, success-type changes and deliberate discard rejection. Rust's numeric error conversion in `test_try` is deliberately replaced by exact E equality; Minyar has no From trait conversion. |
| [Swift SE-0413](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0413-typed-throws.md) and `typed_throws.swift` `testTryIncompatibleTyped`, `testGenericThrownErrorMismatch`, typed closure cases | Reject incompatible propagated error types and preserve callback signatures. No claim to implement Swift throws or its broader effect/subtyping system. |
| [Zig error union reference](https://ziglang.org/documentation/master/#Error-Union-Type) and `error.zig` “error wrapping”, “error return in assignment”, “error union type” | Tagged payload/error distinction and early propagation in a binding. Minyar uses managed ownership cleanup, not Zig's allocator/manual defer model. |
| [Go errors are values](https://go.dev/blog/errors-are-values) and `io_test.go` `TestReadAtLeastWithDataAndEOF`, `TestReadAtLeastWithDataAndError` | Keep outcome separate from byte length and preserve partial data and per-operation errors. No nil/sentinel or mutable last-error substitute for an outcome. |
| Gleam stdlib `result_test.gleam` `try_ok_type_change_test`, `try_error_test`, flatten cases | Nested Result payloads, type-changing success, untouched error propagation and no execution of subsequent work after Err. |
| OCaml `lib-result/test.ml` `test_bind`, `test_join`, `test_fold`, and [pattern documentation](https://ocaml.org/manual/5.4/patterns.html) | Both branches, nested results, explicit recovery and compile-time two-arm completeness. Minyar does not implement arbitrary OCaml patterns or warning-based partial matching. |

## TDD and verification record

The initial red regression commit is `23082e2`. Against the unextended core,
all 14 initial feature tests failed (18 failing assertions with subcases), with
unknown Result types/missing syntax rather than runtime helper behavior.
Sources and exact commands/output/compiler hashes are retained in `errors/red`.

The first native execution run also caught duplicate temporary registration
and missing optimizer-visible cleanup fragments. These caused real use-after-free
and unbalanced function-return failures; they were fixed in the extension
instead of weakening the object accounting oracle. Retained ownership failures
and the final passing manifests are under the task evidence directory.

`tests/errors-language.py` uses the existing exact allocation/debt accounting
runtime at O0 and O2. Normal exits must leave no ownership frames, no deferred
debt after bounded polling, and no non-immortal live objects. Cases include
success/error, nested/early returns, mutable aliases, callback returns/captures,
escaping arm bindings and cyclic graphs through both payload slots.
The suite supports `MINYAR_ERRORS_RUNTIME_FLAGS` to run finite-heap and
poll-budget profiles without changing any global test threshold.
`tests/errors_evidence.py` retains successful as well as failed manifests,
raw per-process output, exact input/output hashes and frozen input snapshots.

The final validation/evidence index will be supplied by the implementation
handoff. Global full-matrix/coverage/performance gates and actual remote Windows
verification belong to the CI integration task and are not claimed here.


## Verified Linux checkpoint, 2026-10-11

All 26 tests pass at both O0 and O2 in each of these sequential profiles:
ordinary heap; ASan/UBSan compiler and applications; 1 MiB bounded heap with
cleanup budgets 1, 32 and 1024; and ASan/UBSan with the same 1 MiB heap and
budget 1. LeakSanitizer is disabled consistently with the repository policy;
the exact live-object/frame/debt assertions remain enabled.

The extended frontend self-hosts with byte-identical stage 2/3 LLVM.
Three in-suite ordinary sources and all five existing codegen fixtures emit
byte-identical IR through core and optional frontends. The maintained core
compiler/runtime sources have no diff against integration base 7f4d0b5.
The largest measured final native compiler link RSS is 134936 KiB; sanitized
link RSS is 201512 KiB, within the unchanged build wrappers' resource limits.
These are compiler-build observations, not a new application performance gate.

A deliberately compiled mutation removing the propagation error-path
`minyar_rc_leave` is rejected by the native execution oracle at both O0 and O2
(actual segmentation faults, rather than a source-only assertion).
The tag-forgery regression was also observed red (unexpected compile success)
before adding the Result record-literal rejection and green afterward.
Per-process manifests, frozen input snapshots, raw outputs, source/LLVM/executable
hashes and the replay fixture sources are retained in
`/home/user/minyar-overnight/errors`. The external handoff index identifies
the exact branch commit, bundles and logs.

Global catalogue/build/launcher wiring and hosted CI, including actual remote
Windows execution, remain integration work for the CI owner. No Windows pass,
full project matrix, unchanged coverage threshold pass or overall overnight
goal completion is claimed by this checkpoint.

