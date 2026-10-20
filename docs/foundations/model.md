# A checked core for ownership and effects

The Lean 4 development under [`proofs/Minyar`](../../proofs/Minyar/Ownership.lean)
defines a small programming-language calculus with resource typing, executable
operational semantics, progress and preservation. It models ownership, borrowing,
scope cleanup, last-use transfer, unique reuse, interrupt effects and DMA phases.
Separate refinements specify completion-witness validation and delayed physical
reclamation. The development proves properties of this calculus; it does not prove
that the full Minyar compiler or C runtime implements it.

The project pins `leanprover/lean4:v4.19.0` and uses only its bundled `Std` library.
The [Lean release](https://lean-lang.org/doc/reference/latest/releases/v4.19.0/)
and [axiom collection implementation](https://github.com/leanprover/lean4/blob/v4.19.0/src/Lean/Util/CollectAxioms.lean)
identify the toolchain and the audit API. No theorem uses `sorry`, a custom axiom,
`native_decide`, or an unsafe definition. `Audit.lean` inspects compiled environment
declarations and recursively collects their axioms. Its exact permitted axioms are
`propext`, `Classical.choice`, and `Quot.sound`; it rejects every other axiom and
every partial declaration in the model and checker modules. Source-written unsafe
definitions also reject. Lean generates unsafe backend implementations even for
total definitions; the audit counts these separately only when their names match
recognized compiler implementation forms and they have no exact source declaration
range. These erased implementations use compiler primitives such as `lcProof`
and are outside the logical axiom audit. Every logical/source declaration,
including all theorems and unreferenced axioms, receives recursive axiom collection.
This distinction audits the kernel's logical declarations without claiming a
verified native code generator. A source declaration cannot gain this exemption
merely by adopting a compiler-looking name: its exact source range takes precedence.
The audit also
examines newly introduced declarations in the `Minyar` namespace, so negative
audit controls cannot hide an unused axiom behind a passing named theorem.
`Contract.lean` additionally asserts the complete types of the required
preservation, affine transfer, no-double-release, public soundness, finite-scope
cleanup, DMA bound and compositional IRQ theorems. A theorem count is only an
audit sanity check; weakening one of those results to `True` fails this contract.

The 2026-10-20 checked snapshot passed the remote foundations target in 20.45 s:
12 modules, 2,756 declarations, and 960 theorem constants, including generated
equations and derived support. The audit examined 1,678 logical declarations and
separately reported 1,078 recognized backend implementations. All five negative
trust controls rejected: unused custom axiom, admitted proof, source unsafe
definition, unsafe definition with a compiler-looking name, and partial definition.
All 27 executable traces passed their acceptance or rejection expectations.
`Examples.lean` additionally kernel-checks public slot-resurrection rejection,
DMA metadata consistency, completion matching and inhabited typing derivations.

## State and operations

A `World` maps allocation identities to `Cell` values and records whether execution
is in interrupt context. An identity denotes one fresh allocation incarnation,
not a raw address that may later be recycled. Each cell contains:

- a lifetime: `fresh`, `live`, `freed`, or permanently `quarantined`;
- lists of owning and borrowed tokens, each with a slot ID and a scope ID;
- a CPU or pending-device phase;
- a free count and a generation incremented by successful reuse.

`Value` distinguishes scalars from references containing an object ID, slot and
capability type. `Capability` is either an owner in a CPU/pending phase or a CPU
borrow. `HasCapability` relates those types to the resource context, and
`ValueTyped` gives references their types in a world. Scalar payload contents and
arithmetic evaluation are abstracted away. A slot belongs to one modeled object;
the model does not prove a correspondence to raw machine pointers. Global slot
naming and lexical scope trees are not separate invariants in the proof. Scope
IDs are labels; an exit removes the tokens with that label.

`UniqueSlots` separately requires that the mapped slot IDs of owners and borrows
together have no duplicates, even when scope labels differ. Every operation
preserves it (`eval_preserves_unique`); `reachable_unique` establishes it for
all finite runs from a fresh cell. `affine_type_soundness` combines typed-program
progress, heap safety and slot uniqueness, and `checker_affine_sound` lifts the
same invariants to executable world replay. This prevents releasing or moving one
slot from silently deleting several distinct ownership obligations.

The public `Resource` additionally carries a persistent `nextSlot` watermark.
Allocation sets it to `owner + 1`. Every public retain, move, borrow and reuse
requires a destination at least that watermark, then advances the watermark to
`destination + 1`. `SlotsBelow` puts every active owner or borrow below it.
Skipped numbers are conservatively reserved; the model never reissues an old
numeric capability. The watermark is an unbounded natural number, so wrapping
machine-word representations require a separate implementation argument.

`DeadSlot` means an absent capability number below the watermark; `DeadAt` locates
it at a persistent resource index. Move, reuse, release and end-borrow establish
that condition for their consumed slot. `program_dead_preserved` and
`stale_capability_never_returns` prove that any later well-typed public program
preserves its absence and rejects both use and release of it. This includes
intervening allocation, DMA and interrupt actions. In particular, move `0 → 1`
followed by retain `1 → 0` rejects. The lower diagnostic cell interpreter checks
current token membership; the public calculus supplies this stronger historical
identity property.

`alloc` creates the first owner of a fresh identity. `retain` adds an owner after
checking a source owner and an unused destination slot. `move` removes the source
owner and creates a destination owner without changing allocation liveness.
`borrow` creates a non-owning token; `endBorrow` removes it. `use` requires a live,
CPU-accessible cell and an existing owner or borrow token. A release removes its
owner; removal of the last owner succeeds only when no borrow remains. A cell
then becomes permanently freed. An exit ends its scope's borrows before releasing
its scope's owners, and rejects if an external borrow would lose its last owner.

`reuse` requires exactly one owner and no borrows, consumes that owner, installs a
fresh destination token, and increments the generation. This models the successful
unique-storage branch of a Perceus-style consumer. An aliased runtime consumer
must use the ordinary copy/allocation-and-release path; uniqueness is not inferred
from last use. The model has no source-level future-use analysis: it checks the
resulting token transfer. A real compiler may select a consuming operation only
after all argument evaluations and earlier reads have completed, as described in
[compiler syntax](../compiler-syntax.md).

The guards in `eval` test concrete token membership, lifetime and phase conditions.
They never call `WellFormed`. In particular, the preservation theorem is not
obtained by defining an accepted transition to require the full safety invariant.
The world-level `step` updates exactly the selected cell and rejects all heap
operations while in interrupt context.

## Theorems and their exact meaning

The `Typed` judgment in `Typing.lean` is defined independently by inductive
resource rules. A move needs a CPU owner and a fresh destination; a borrow needs
that owner and a fresh loan slot; final release and scope exit need a proof that
no external loan loses its last owner. Reuse and DMA submission require one owner
and no loans. Bare `complete` has no typing constructor
(`raw_completion_not_typable`); its implementation is an internal acquired-witness
transition. These rules contain
neither an invocation of `eval` nor the full `WellFormed` invariant.
`typed_progress` proves that every typed command executes to its prescribed
result. `typed_preservation` proves that it preserves safety. `TypedProgram`
threads resource contexts through a finite command sequence; `type_soundness`
proves both an operational run and a well-formed final state. This is resource
type soundness for the small calculus, not source-language type soundness for
every Minyar syntax form.

The public syntax and semantics are in `Language.lean`. `OwnerOp` has no raw
completion constructor. Submission saves a canonical `Request` in its finite
`Resource`, including its owner, cell generation, device/queue identity, capacity
and a fresh request serial. `State.nonce` is the maximum saved serial across the
persistent finite context, including freed and quarantined resources. Submission
seeds its request from that global floor and strictly advances it; the action and
program nonce theorems prove it cannot reset. Thus a different allocation reusing
a reclaimed queue still rejects the old completion. `historical_replay_rejected`
composes a first typed submission, any intervening typed public program, and a
new canonical submission to prove rejection of the first request's nonce.
Active requests block another submission to the same queue. Retirement preserves the private request metadata,
permanently blocking that quarantined queue while consuming its affine handle.
Public reclaim accepts only a `Completion` and compares it with that stored current request. It cannot replace the request
with another snapshot. `stale_request_rejected`, `forged_device_rejected` and
`no_request_rejected` give direct public rejection corollaries. `Examples.lean`
checks a successful submit/reclaim, a second submission rejecting its predecessor's
completion, queue reuse by a different allocation, forged fields, overrun, wrong
owner, and terminal quarantine. It also constructs an inhabited `ProgramTyped`
borrow/read/end-borrow/release sequence and a compositional interrupt derivation
through a call and branch, with a matching execution trace.

`State` contains a finite resource context and an independent heap of allocation
bits, payloads and current-request metadata. `Consistent` relates a supplied
initial context to that heap and requires well-formed, unique resource slots,
the persistent slot bound, DMA request/phase coherence, and context-wide queue
uniqueness. Ordinary CPU, fresh and freed resources carry no request. Pending and
quarantined resources carry a request bound to their cell generation and capacity,
with positive submitted length within capacity and a nonzero generation no greater
than the persistent serial. A pending request names an actual owner slot. No two
resources may carry the same queue capability, including quarantined queues.
Every location outside the finite context must be unallocated, so the relation
cannot hide an owned allocation outside its domain.
`ActionTyped` and `ProgramTyped` are independent inductive judgments;
`action_type_soundness` and `public_type_soundness` prove progress and preservation
from any such consistent initial state. `public_read_allocated` derives that a
typed read's storage is allocated, rather than assuming an arbitrary heap is
valid. Store synchronization specifies abstract allocation/release and registry
updates; proving a concrete allocator implements it remains outside this model.
`public_context_coherence` exposes preserved resource validity, queue uniqueness
and request coherence explicitly. `canonical_reclaim_origin` proves that a
successful reclaim consumed the exact stored, bound request, matched the supplied
completion and cleared the registry entry. `quarantined_queue_poisoned` derives
permanent submission rejection for the queue of any consistent quarantined resource.

`WellFormed` states that a cell is live exactly when it has an owner, non-live
cells have no borrows, pending DMA has one owner and no borrows, and its free count
is one exactly when it is freed. The development proves:

- `eval_preserves`, `runs_preserves`, and `step_preserves`: operational steps and
  finite runs preserve that invariant, starting from empty fresh cells.
- `use_valid`: every accepted read has a live CPU cell and a present token.
  `borrow_valid`: every outstanding borrow in a well-formed state has a live cell,
  including between reads. Together these exclude modeled use after free.
- `no_double_free`, `freed_terminal`, and `freed_run_empty`: each allocation
  incarnation is freed at most once, every operation on a freed identity rejects,
  and a run starting freed can only be empty. This does not cover
  an allocator incorrectly reusing an identity for a later physical allocation.
- `moved_source_absent`: removing a source slot removes that owner from its token
  list. A move is not a proof that the source program has no later references;
  subsequent commands must still satisfy the resource typing rules.
- `move_invalidates_source`, `borrow_postcondition`, `reuse_postcondition` and
  `release_once` strengthen the local rules: a move prevents reading its source,
  a borrow preserves its owners and creates its loan, reuse requires exclusive
  ownership and advances its generation, and releasing a token cannot release
  that token again without an explicit operation introducing a new owner there.
- `wrong_owner_move_rejected`, `borrowed_last_owner_rejected`, and
  `shared_reuse_rejected`: an absent source owner cannot be consumed, a final
  owner cannot disappear under an outstanding loan, and aliased storage cannot
  enter the unique reuse branch.
- `scope_no_leak`: a live CPU allocation whose remaining owners and borrows all
  belong to the exiting scope becomes freed, with empty owners and borrows and
  exactly one free. Shared owners in other scopes deliberately keep an allocation
  alive. A pending DMA allocation is not eligible for this cleanup theorem.
- `pending_no_cpu_access`, `submit_affine`, and
  `completion_requires_pending`: submission requires one owner and no borrows;
  pending buffers cannot be read, released, borrowed or reused by CPU operations;
  completion is permitted only in the pending phase and returns the CPU phase.
- `retire` consumes the sole pending handle into `quarantinedCell`, with no owner
  or borrow tokens and no physical free. `quarantined_terminal` proves that this
  state cannot be read, completed, freed or reused; `quarantine_keeps_backing`
  makes its deliberately pinned storage explicit. Ordinary CPU `release` models
  disposal, while pending disposal is prohibited.
- `irq_excludes_heap` and `irq_effect_safe`: IRQ execution cannot operate on the
  managed heap or DMA capabilities. Its accepted effect labels are only scalar,
  fixed-width MMIO/port access and interrupt signaling. Managed allocation,
  Float, blocking, lock, native, indirect and cyclic-call effects reject.
- `checker_sound`: successful executable `replay` from `initialWorld` yields a
  well-formed world. It uses exactly the same `step` definition as the proofs.

These are finite-program resource progress, safety and conditional cleanup
results. They do not establish that all source programs are accepted or that
arbitrary machine instructions satisfy the rules. The model can reject cases that
the runtime handles safely by retaining additional temporary owners.

## Frames, polling and the explicit cycle policy

`Finite.lean` gives a world-level scope rule over a finite list of resources.
`ContextLocal` requires that every live resource is in the CPU phase and all its
remaining owners and loans belong to the exiting scope. Terminal freed or
quarantined resources may also be present. `finite_scope_cleanup` proves successful
cleanup of the entire context, with no live owner or borrow left, an exact charge
of one reclamation obligation per newly closed finite resource, and preservation
of the intentionally pinned quarantine count. `scope_no_leak_modulo_policy`
composes this with polling: after sufficient service, remaining obligations are
exactly traced-cycle debt plus the original quarantined backing.
`program_scope_cleanup` composes public program soundness with this exit rule;
it explicitly requires a local final context and a return from interrupt mode.
Its post-exit state is consistent with the closed context, and
`closed_store_only_quarantine` proves that every remaining addressable allocation
belongs to explicitly quarantined backing. Queued physical work and cycle debt
remain separately recorded by the reclamation refinement.
`close_context_request_shrink` proves that exit can only preserve or remove saved
requests; `close_context_queues_unique` consequently preserves queue uniqueness
and the quarantined queue's identity through finite scope cleanup.

`Reclamation.lean` separates logical owner release from physical destruction.
`Ledger` records queued acyclic work, uncollected traced-cycle work and reclaimed
work. `retire` adds a finite component's obligations to the correct category.
`exitScope` links a fully local scope's logical release to that debt;
`scope_exit_records_debt` proves the connection. A work unit abstracts one
destructor/edge obligation. Component sizes and graph classification are supplied
by a runtime interpretation, rather than discovered by this calculus.

`poll` services the minimum of its budget and queued work. `poll_work_bound`
proves that it never exceeds the budget; `poll_preserves_accounting` and
`polls_accounting` prove that service never erases obligations without recording
reclamation. `polls_queued` computes the remaining queued work after a finite
budget sequence, and `finite_service_drains` proves that sufficient total service
drains it. Neither a fairness assumption nor eventual future calls to `poll` is
silently inferred.

The policy for cycles is explicit: polling cannot remove the `cycles` debt.
`drain_modulo_cycles` proves that sufficient polling leaves exactly that debt.
Only `collect`, an abstract event supplied by a separate correct traced collector,
may transfer cycle obligations into the ordinary queue.
`collect_preserves_accounting` proves that this transfer loses no debt;
`collect_then_drain` proves complete cleanup given that event and enough service.
Thus the scope-exit no-leak claim is conditional on finite component accounting,
and eventual physical cleanup is conditional on cycle collection and polling.

## Runtime and hardware boundaries

The current runtime uses non-atomic RC within one execution domain. Each abstract
owner stands for a real ownership obligation, including local slots, temporaries,
retained heap edges or returned values. The model does not verify C pointer
arithmetic, LLVM attributes, counter overflow, header layout, identity lookup or
the correctness of a foreign function. Null and immortal values are outside the
allocated-resource domain and need a separate runtime interpretation.

Logical cleanup is atomic; physical cleanup uses the explicit ledger above.
Treating a logically freed allocation as unusable is conservative while real
storage remains queued. The development proves the abstract budget/accounting
properties, not C queue correctness, the correspondence between C work units and
the ledger, or the release of every edge in a concrete heap graph. Those remain
obligations of the [bounded runtime contract](../bounded-runtime-contract.md).

The language activates traced components for cycle-capable mutation and closure
edges, as documented in [runtime memory](../runtime-memory.md). The ledger models
their explicit cleanup obligation, but the graph algorithm that identifies and
collects unreachable cycles is not verified here. The calculus does not silently
declare an unreachable cycle reclaimed merely because its local owners exited.

`Dma.lean` refines `complete` with frozen `Request` and `Completion` snapshots.
`Dma.reclaim` checks matching device, queue, slot, request generation, queue epoch,
publication sequence and nonzero publication, plus completed length bounded by
both submitted and allocated capacity. `reclaim_matches`, `reclaim_prefix_bounded`
and `reclaim_preserves` prove identity, bounds, phase and ownership safety.
The individual mismatch theorems cover the seven deterministic-runtime corruption
fields: device, queue, descriptor slot, request generation, length, queue epoch
and publication sequence. Length has separate submitted-limit and capacity-limit
theorems. `reclaim_binds_capability`, `wrong_owner_rejected` and
`stale_cell_generation_rejected` additionally bind the request's `ownerSlot` and
`cellGeneration` to the actual cell capability. The descriptor slot is distinct
from the capability's owner slot.

The lower `Dma.reclaim` helper assumes its request is current. The public language
establishes that association by storing the canonical request at submission and
reading it back at reclaim; the caller cannot supply a replacement request.
Connecting this abstract registry to the C queue's active-allocation pointer is
still a runtime-refinement obligation. Snapshot acquisition, acquire/release ordering,
coherent memory, IOMMU mappings and cache maintenance are not proved. The virtio
backend's one-shot fresh compliant device assumption is separate from the
deterministic witness model. The calculus assumes serialized boot-CPU use and
models retirement as terminal quarantine with deliberately pinned backing, which
is excluded from ordinary no-leak cleanup. A timeout or unvalidated IRQ is not a completion witness. No safe-reset
or arbitrary-thread reclaim theorem is asserted.

`Effects.lean` gives terms, sequences, branches, calls and function bodies a
compositional effect judgment. An action's effect is determined by its syntax;
call effects must be derived from the actual callee body, and both branches are
checked. `effects_cover_execution` proves that every executed action's effect is
covered by the derivation. `interrupt_execution_safe`, `interrupt_no_ownership`,
`interrupt_no_allocation` and `interrupt_no_blocking` consequently exclude the
targeted operations through nested calls and branches. `function_type_soundness`
combines those derivations with resource-typed execution. This is a theorem for
the term calculus; the mapping from source/native instructions to its primitives,
physical stack bounds, interrupt ABI, preemption and hardware entry remain
outside the proof. Calls need a finite derivation, so recursive call cycles have
no unchecked-summary rule.

## Running and consuming the checker

Build and audit on the authorized build host:

```sh
cd proofs
lake build ownership-check
lake env lean Audit.lean
```

The repository check target `make -f build-support/foundations.mk check-foundations-proofs`
performs that sequential build/audit, runs the five trust controls and exercises
the executable traces. Its evidence records source hashes and command exit codes.

The binary is `build/foundations-lean/bin/ownership-check` relative to the repository
root. It reads newline-separated commands from standard input, accepts blank lines
and whole-line `#` comments, and accepts only decimal natural numbers as IDs. Fields
are separated by spaces. Its successful result is `ok N`, where N is the number
of commands. Parse failures and invalid transitions print `error line N: parse`
or `error line N: rejected` on standard error and exit nonzero. Inputs are capped
at one million lines and reject if they reach the cap before EOF. The parser and
IO driver are outside the logical `checker_sound` statement; every accepted parsed
command is nevertheless executed by the proved `step` function.

```text
alloc object slot scope
retain object sourceSlot destinationSlot scope
move object sourceSlot destinationSlot scope
borrow object sourceSlot borrowSlot scope
endborrow object borrowSlot
use object slot
release object ownerSlot
reuse object sourceSlot destinationSlot scope
exit object scope
submit object ownerSlot
retire object ownerSlot
irq_enter
irq_exit
effect scalar|mmio|signal|managed|float|blocking|lock|native|indirect|cyclic
```

`exit` is per object. A successful trace need not be leak free merely because it
was accepted: its remaining owners may intentionally belong to another scope.
The no-leak and delayed-reclamation theorems require their stated cleanup premises.
The CLI exercises lower ownership semantics. Bare `complete` is deliberately
rejected; successful public DMA reclaim is checked through the executable pure
`Language.resourceEval` function and its kernel-checked examples. The public
function/resource typing and finite scope theorems are the soundness contract.
