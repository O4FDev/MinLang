# Recovery adapter composition contract

`compiler/build-calldepth-compiler.py` exports `adapt(source) -> source`.
Call it after the closure/Result assembly and the thread adapter. `assemble()`
is the standalone nonthreaded entry point. Every replacement uses checked
anchors and fails on incompatible emitter structure; it never overwrites a
thread adapter's complete source with a snapshot. The ordinary core and its
frozen reconstruction digest stay unchanged.

The emitter state keeps existing slots 0–14. Additional state must start at 15.
Recovery entry labels are `recovery.reject` and `recovery.body`; accepted
failures branch to `recovery.unwind`. Immediate named and indirect checkpoints
create unique `recovery.continue.*` labels and update `textState[0]` to the
actual continuation predecessor before later PHIs. Callback header/domain
validation precedes the body; boundary domain validation precedes all depth
scope mutation. `calldepth.run` and `remaining` are dedicated boundaries.

Module constant loaders and `sortBy`/`sortedBy` comparators reenter language
code, so their call sites checkpoint too; `sortedBy` releases its fresh result
on the unwind edge. A rejected or unwound constant initializer resets the
constant to uninitialized, so a later read retries it.

Stack ownership requires `state[14] == 0`, including indirect calls. The
adapter rewrites only the exact RC entry piece and each exact RC leave piece,
using stack_v1's matching leave. It preserves callback domain/header metadata
and does not assume the definition tail is at entry slot minus one. A thread
adapter must coordinate any different RC entry/leave pieces and preserve
paired accepted entries and exits, including Result `try` and native wrappers.

Every emitted recovery graph has marker
`minyar-calldepth-policy: cooperative-v1-full-program`. The public launcher
uses request status 88 and bypasses module reuse even for `--incremental`.
Recovery code is a separate full-program frontend, so ordinary caches cannot
be used for any transitive language module.

`errors.callDepthCode()` is 14; checked arithmetic reserves code 13. These
runtime error values do not share a namespace with WS1's nominal type tags
9–15. All scope, reporting, depth and native-bound state uses the reviewed
numeric `MINYAR_THREAD_LOCAL` selector. This API is offered for composition;
threaded managed ownership still needs WS1 implementation and independent
review, and the full combined platform/performance gates remain outstanding.
