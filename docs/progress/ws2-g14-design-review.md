# G14 independent design review R1

Read-only audit of clean `bf9c0e9`, task
`ws2-g14-readonly-design-audit-r1-20261012`. Result consumed after authoritative
terminal status. No implementation, tests/builds, Boat operations/spending,
commits or nested tasks. Cooperative returns are feasible, but the draft design
does not yet cover all relevant calls, ownership and control flow.

## Required emitter changes

- `compiler/compiler.min:3922` emits named calls directly; the core `emitCall`
  helper is insufficient. `compiler/closure-compiler.min:392` emits indirect
  callback calls separately. Check pending failure after each completed call,
  before `parsePrimary` registers/projects the result (`compiler.min:2580`).
  A statement-level checkpoint fails for `sink(deep(), readTextFile(path))`:
  later arguments already execute at `compiler.min:3747`. A dummy managed
  callback return must never be consumed by `.field` or `.slice()`.
- `compiler.min:1624` erases prior owner registration when transferring a
  temporary. `freshText() + deepText()` later removes the left owner
  (`1885–1888`), while recovery from the right operand bypasses that join.
  `makeList().appended(deep())` has the same issue (`2644–2649`). Preserve
  registration across intervening fallible evaluation. A conservative first
  recovery emitter can disable these `takeOwner` transfers.
- Lists allocate at `compiler.min:3289` before evaluating elements (`3305`),
  and register only when construction completes. Root the partially built List
  immediately, exactly once. Records register early (`2870`), but later
  assignment/return `takeResult` can erase that registration. Preserve it until
  construction successfully completes. Tests need `[freshText(), deepText()]`
  and `Box { text: freshText(); number: deep() }`. Zeroed record values/maps
  support partial destruction (`runtime/minyar_cycle_collections.h:320`).
- Entry rejection before RC/depth acceptance returns a typed dummy with no
  leave; propagation inside an accepted function performs matching RC and
  stack leaves. Cover ordinary entry (`compiler.min:1781`), explicit return
  (`5170`), native wrapper (`4569`), ordinary/top-level fallthrough (`5454`,
  `5575`), callback fallthrough (`closure-compiler.min:465`), and Result `try`
  return (`errors-compiler.min:264`).
- Use matching `minyar_rc_leave_stack_v1` for stack-backed frames. Generic
  bounded leave queues storage (`runtime/minyar_cycle_rc.h:364`), which would
  dangle for a stack header. Stack ownership eligibility uses `state[5]` while
  indirect calls update only `state[14]`: a Bytes-owning callback wrapper can
  qualify as nonleaf (`compiler.min:5491`, `closure-compiler.min:399`). Existing
  `finishStackOwnership` also assumes slot−1 is the definition tail (`1771`),
  but callback emission places domain validation there (`closure:438`). Adapt
  structured entry metadata; do not reuse the optimization unchanged.
- Leaf/tree guard elision (`compiler.min:5503`, `4977`), parallel guard removal
  (`4837`), machine entry removal (`5487`) and unchecked `machine.callEntry`
  (`4650`) require explicit treatment. Ordinary code can call recursive parallel
  functions; `checkParallelCalls` restricts only parallel callers (`4996`).
  Retain logical guards/recovery variants throughout supported transitive
  language calls and define raw-entry behavior. Do not silently bypass the
  depth guarantee or claim unchecked edges are instrumented.
- Every checkpoint continuation updates `textState[0]`, used by short-circuit
  PHIs (`compiler.min:2047`, `2063`). Entry splitting preserves actual body
  predecessor. Integer-dispatch lowering hardcodes `%entry`, replaces the body
  and embeds stack leaves (`3272`); adapt structurally or disable this
  optimization specifically for recovery emission.

## Boundary, runtime and caching

Add a separate status-returning entry guard; `minyar_stack_enter_slow`
(`runtime/minyar_runtime.c:172`) currently calls the fatal stop. Increment depth
only on acceptance. Preserve ordinary guard and ASan native-stack-marker
exclusion (`193`). Detected native reserve failure can unwind cooperatively;
actual guard-page overflow from large generated/native prologues can happen
before the entry hook and is not proved covered by this proposal.

The boundary validates callback domain before touching state, saves/restores
nested scope state, clamps inner allowance to parent remaining capacity and
intercepts failure before generic propagation. Construct through existing
`errors.integer`/`integerFailure` factories. Ordinary native wrappers cannot
accept Callback or return IntegerResult (`compiler.min:4473`, `4545`, `4556`),
so dedicated boundary lowering is needed. Define root callback as one frame,
noncounting `remaining()` intrinsic, zero/negative-limit behavior and query
outside a scope. Reporting machinery must not itself exhaust the allowance it
reports. Remaining is advisory because native reserve can reject first. Already
completed side effects survive; recovery does not roll them back.

Whole-program import flattening (`compiler.min:6388`) permits transitive
instrumentation. Per-module incremental reuse (`module-compiler.min:813`) must
salt recovery policy into graph/context/cache identity or use full compilation;
compiler identity alone does not distinguish modes in one compiler.

The fixed foundation comparator in `scripts/build-closure-compiler.py:155`
hashes the entire reconstructed source. Prefer guarded recovery adapters after
closure/Result assembly to leave ordinary core unchanged where possible. If
core changes are necessary, coordinate the shared pinned frozen-source solution
with WS3/integrator; keep `a5f30a…` digest and current optional-frontends intact.
The reviewer alternatively identifies reviewed fail-closed inverse
reconstruction; no silent digest update is allowed.

## WS1 dependency

`c38057c` remains unapproved: `#ifdef MINYAR_THREADED` enables TLS for `=0`,
and explicit boundedRC without system heap selects an implicit pool despite
guards. Await corrected/reviewed absent/0 ordinary, 1 threaded, invalid-values
rejected contract. Threaded boundedRC requires system heap; actual eager
malloc/free is allowed. Apply corrected `MINYAR_THREAD_LOCAL` to recovery and
all depth/bounds state (`runtime/minyar_runtime.c:124`). This review does not
approve or integrate the existing config commit.

All above requirements need test-first implementation and runtime evidence
after Phase 1 release. This is design evidence, not a correctness pass or
permission to skip any acceptance gate.
