import Minyar.Finite

namespace Minyar.Language

open Finite

/-- Public ownership syntax deliberately has no raw completion operation. -/
inductive OwnerOp where
  | retain (source target scope : Nat)
  | move (source target scope : Nat)
  | borrow (source target scope : Nat)
  | endBorrow (slot : Nat)
  | use (slot : Nat)
  | release (slot : Nat)
  | reuse (source target scope : Nat)
  deriving DecidableEq, Repr

def OwnerOp.lower : OwnerOp → Op
  | .retain a b s => .retain a b s
  | .move a b s => .move a b s
  | .borrow a b s => .borrow a b s
  | .endBorrow a => .endBorrow a
  | .use a => .use a
  | .release a => .release a
  | .reuse a b s => .reuse a b s

def OwnerOp.target : OwnerOp → Option Nat
  | .retain _ target _ | .move _ target _ | .borrow _ target _ | .reuse _ target _ => some target
  | _ => none

def OwnerOp.fresh (nextSlot : Nat) : OwnerOp → Prop
  | .retain _ target _ | .move _ target _ | .borrow _ target _ | .reuse _ target _ => nextSlot ≤ target
  | _ => True

instance (nextSlot : Nat) (operation : OwnerOp) : Decidable (operation.fresh nextSlot) := by
  cases operation <;> dsimp [OwnerOp.fresh] <;> infer_instance

def OwnerOp.advance (nextSlot : Nat) : OwnerOp → Nat
  | .retain _ target _ | .move _ target _ | .borrow _ target _ | .reuse _ target _ => target + 1
  | _ => nextSlot

theorem owner_cursor_monotone {operation : OwnerOp} (fresh : operation.fresh cursor) :
    cursor ≤ operation.advance cursor := by
  cases operation <;> simp_all [OwnerOp.fresh, OwnerOp.advance] <;> omega

theorem owner_target_fresh {operation : OwnerOp}
    (fresh : operation.fresh cursor) (target : operation.target = some slot) :
    cursor ≤ slot := by
  cases operation <;> simp_all [OwnerOp.fresh, OwnerOp.target]

theorem owner_target_below {operation : OwnerOp} (target : operation.target = some slot) :
    slot < operation.advance cursor := by
  cases operation <;> simp_all [OwnerOp.target, OwnerOp.advance]

theorem active_new_owner (active : Active (liveCell (token :: owners) borrows phase generation) slot) :
    token.slot = slot ∨ (has owners slot ∨ has borrows slot) := by
  rcases active with owned | borrowed
  · rcases owned with ⟨item, member, same⟩
    rcases List.mem_cons.mp member with first | rest
    · subst item
      exact .inl same
    · exact .inr (.inl ⟨item, rest, same⟩)
  · exact .inr (.inr borrowed)

theorem active_new_borrow (active : Active (liveCell owners (token :: borrows) phase generation) slot) :
    token.slot = slot ∨ (has owners slot ∨ has borrows slot) := by
  rcases active with owned | borrowed
  · exact .inr (.inl owned)
  · rcases borrowed with ⟨item, member, same⟩
    rcases List.mem_cons.mp member with first | rest
    · subst item
      exact .inl same
    · exact .inr (.inr ⟨item, rest, same⟩)

theorem cleanup_active (active : Active (cleanupResult owners borrows generation) slot) :
    has owners slot ∨ has borrows slot := by
  unfold cleanupResult at active
  split at active
  · simp [Active, freedCell, has] at active
  · exact active

/-- Existing numeric capabilities can only survive; a new one must be the
    operation's explicitly fresh destination. -/
theorem owner_active_origin {operation : OwnerOp} (typing : Typed cell operation.lower next)
    (active : Active next slot) : Active cell slot ∨ operation.target = some slot := by
  cases operation with
  | retain source target scope =>
    cases typing with
    | retain capability unused =>
      rcases active_new_owner active with same | old
      · exact .inr (congrArg some same)
      · exact .inl old
  | move source target scope =>
    cases typing with
    | move capability unused =>
      rcases active_new_owner active with same | old
      · exact .inr (congrArg some same)
      · rcases old with owned | borrowed
        · exact .inl (.inl (has_sublist List.filter_sublist owned))
        · exact .inl (.inr borrowed)
  | borrow source target scope =>
    cases typing with
    | borrow capability unused =>
      rcases active_new_borrow active with same | old
      · exact .inr (congrArg some same)
      · exact .inl old
  | endBorrow ended =>
    cases typing with
    | endBorrow capability =>
      rcases active with owned | borrowed
      · exact .inl (.inl owned)
      · exact .inl (.inr (has_sublist List.filter_sublist borrowed))
  | use used => cases typing <;> exact .inl active
  | release released =>
    cases typing with
    | release capability safe =>
      rcases cleanup_active active with owned | borrowed
      · exact .inl (.inl (has_sublist List.filter_sublist owned))
      · exact .inl (.inr borrowed)
  | reuse source target scope =>
    cases typing with
    | reuse capability unused unique noLoans =>
      rcases active_new_owner active with same | old
      · exact .inr (congrArg some same)
      · simp [has] at old

theorem owner_slots_below {operation : OwnerOp}
    (known : SlotsBelow cell cursor) (fresh : operation.fresh cursor)
    (typing : Typed cell operation.lower next) : SlotsBelow next (operation.advance cursor) := by
  intro slot active
  rcases owner_active_origin typing active with old | target
  · exact Nat.lt_of_lt_of_le (known slot old) (owner_cursor_monotone fresh)
  · exact owner_target_below target

theorem owner_dead_preserved {operation : OwnerOp}
    (dead : DeadSlot resource slot) (fresh : operation.fresh resource.nextSlot)
    (typing : Typed resource.cell operation.lower next) :
    DeadSlot { resource with cell := next, nextSlot := operation.advance resource.nextSlot } slot := by
  refine ⟨Nat.lt_of_lt_of_le dead.1 (owner_cursor_monotone fresh), ?_⟩
  intro active
  rcases owner_active_origin typing active with old | target
  · exact dead.2 old
  · have lower : resource.nextSlot ≤ slot := owner_target_fresh fresh target
    have below : slot < resource.nextSlot := dead.1
    omega

theorem owner_result_cpu {operation : OwnerOp}
    (typing : Typed cell operation.lower result) :
    result.phase = .cpu ∧ result.life ≠ .quarantined := by
  cases operation <;> cases typing <;>
    simp_all [HasCapability, cleanupResult, liveCell, freedCell] <;>
    split <;> simp_all [liveCell, freedCell]

inductive LocalAction where
  | owner (op : OwnerOp)
  | submit (owner device queue descriptor queueEpoch length : Nat)
  | reclaim (owner : Nat) (completion : Dma.Completion)
  | retire (owner : Nat)
  deriving DecidableEq, Repr

def AddsQueue : LocalAction → Nat → Prop
  | .submit _ _ queue _ _ _, other => other = queue
  | _, _ => False

def FreshQueues (context : Context) (action : LocalAction) : Prop :=
  ∀ resource ∈ context, ∀ request, resource.request = some request → ¬ AddsQueue action request.queue

/-- The finite context is never truncated. Its maximum saved serial is therefore
    a persistent global nonce, including disposed and quarantined allocations. -/
def contextNonce (context : Context) : Nat :=
  context.foldr (fun resource nonce => max resource.serial nonce) 0

@[simp] theorem contextNonce_cons : contextNonce (resource :: rest) =
    max resource.serial (contextNonce rest) := rfl

def isSubmit : LocalAction → Bool
  | .submit .. => true
  | _ => false

def queueAvailable (context : Context) : LocalAction → Bool
  | .submit _ _ queue _ _ _ => context.all fun resource =>
      match resource.request with
      | none => true
      | some request => request.queue != queue
  | _ => true

theorem busy_queue_unavailable (member : resource ∈ context)
    (current : resource.request = some request) (same : request.queue = queue) :
    queueAvailable context (.submit owner device queue descriptor queueEpoch length) = false := by
  change context.all (fun item => match item.request with
    | none => true | some pending => pending.queue != queue) = false
  induction context with
  | nil => simp at member
  | cons head rest ih =>
    simp only [List.all_cons]
    rcases List.mem_cons.mp member with eq | tail
    · subst head
      simp [current, same]
    · simp [ih tail]

theorem queue_available_fresh (available : queueAvailable context action = true) :
    FreshQueues context action := by
  intro resource member request current added
  cases action with
  | submit owner device queue descriptor queueEpoch length =>
    have rejected : queueAvailable context
        (.submit owner device queue descriptor queueEpoch length) = false :=
      busy_queue_unavailable member current added
    simp [available] at rejected
  | owner operation => exact added
  | reclaim owner completion => exact added
  | retire owner => exact added

/-- Seed every resource with the global floor before submission. Only the chosen
    resource receives floor+1; current pending requests themselves are untouched. -/
def prepare (context : Context) (action : LocalAction) : Context :=
  if isSubmit action then
    context.map fun resource => { resource with serial := contextNonce context }
  else context

theorem serial_request_shrink (context : Context) (serial : Nat) :
    RequestShrink (context.map fun resource => { resource with serial := serial }) context := by
  induction context with
  | nil => exact .nil
  | cons resource rest ih => exact .cons (fun _ current => current) ih

theorem prepare_request_shrink (context : Context) (action : LocalAction) :
    RequestShrink (prepare context action) context := by
  unfold prepare
  split
  · exact serial_request_shrink _ _
  · exact request_shrink_refl _

theorem prepare_queues (unique : QueuesUnique context) : QueuesUnique (prepare context action) :=
  queues_shrink unique (prepare_request_shrink _ _)

theorem prepare_fresh (available : queueAvailable context action = true) :
    FreshQueues (prepare context action) action := by
  intro resource member request current
  rcases request_shrink_member (prepare_request_shrink context action) member current with
    ⟨prior, oldMember, oldCurrent⟩
  exact queue_available_fresh available prior oldMember request oldCurrent

theorem contextNonce_bound (member : resource ∈ context) : resource.serial ≤ contextNonce context := by
  induction context with
  | nil => simp at member
  | cons head rest ih =>
    simp only [contextNonce_cons]
    rcases List.mem_cons.mp member with eq | member
    · subst resource
      exact Nat.le_max_left _ _
    · exact Nat.le_trans (ih member) (Nat.le_max_right _ _)

inductive SerialOrder : Context → Context → Prop where
  | nil : SerialOrder [] []
  | cons : first.serial ≤ second.serial → SerialOrder left right →
      SerialOrder (first :: left) (second :: right)

theorem serial_order_refl (context : Context) : SerialOrder context context := by
  induction context with
  | nil => exact .nil
  | cons head rest ih => exact .cons (Nat.le_refl _) ih

theorem serial_order_nonce (order : SerialOrder left right) : contextNonce left ≤ contextNonce right := by
  induction order with
  | nil => exact Nat.le_refl _
  | cons head tail ih =>
    simp only [contextNonce_cons]
    exact Nat.max_le_of_le_of_le
      (Nat.le_trans head (Nat.le_max_left _ _))
      (Nat.le_trans ih (Nat.le_max_right _ _))

theorem raise_serial_order (bound : ∀ resource ∈ context, resource.serial ≤ nonce) :
    SerialOrder context (context.map fun resource => { resource with serial := nonce }) := by
  induction context with
  | nil => exact .nil
  | cons head rest ih =>
    exact .cons (bound head (by simp))
      (ih (fun resource member => bound resource (by simp [member])))

theorem prepare_order (context : Context) (action : LocalAction) :
    SerialOrder context (prepare context action) := by
  unfold prepare
  split
  · exact raise_serial_order (fun resource member => contextNonce_bound member)
  · exact serial_order_refl _

theorem prepare_valid (valid : ContextValid context) : ContextValid (prepare context action) := by
  unfold prepare
  split
  · intro resource member
    rcases List.mem_map.mp member with ⟨original, originalMember, eq⟩
    subst resource
    have originalValid := valid original originalMember
    exact ⟨originalValid.1, originalValid.2.1,
      request_coherent_raise originalValid.2.2.1 (contextNonce_bound originalMember),
      originalValid.2.2.2⟩
  · exact valid

theorem prepare_submit_floor
    (member : resource ∈ prepare context (.submit owner device queue descriptor queueEpoch length)) :
    resource.serial = contextNonce context := by
  change resource ∈ context.map (fun item => { item with serial := contextNonce context }) at member
  rcases List.mem_map.mp member with ⟨original, originalMember, eq⟩
  subst resource
  rfl

def submitted (resource : Resource) (owner device queue descriptor queueEpoch length : Nat) :
    Dma.Request :=
  ⟨owner, resource.cell.generation, device, queue, descriptor, resource.serial + 1,
    queueEpoch, length, resource.capacity⟩

def resourceEval (resource : Resource) : LocalAction → Option Resource
  | .owner op =>
    if resource.request = none ∧ op.fresh resource.nextSlot then
      (eval resource.cell op.lower).map fun next =>
        { resource with cell := next, nextSlot := op.advance resource.nextSlot }
    else none
  | .submit owner device queue descriptor queueEpoch length =>
    if resource.request = none ∧ 0 < length ∧ length ≤ resource.capacity then
      (eval resource.cell (.submit owner)).map fun next =>
        { resource with
          cell := next
          request := some (submitted resource owner device queue descriptor queueEpoch length)
          serial := resource.serial + 1 }
    else none
  | .reclaim owner completion => do
    let request ← resource.request
    let view ← Dma.reclaim resource.cell owner request completion
    pure { resource with cell := view.cell, request := none }
  | .retire owner =>
    (eval resource.cell (.retire owner)).map fun next =>
      { resource with cell := next }

/-- The request is stored at submission. Reclaim cannot accept a caller-chosen
    replacement request, even if that replacement matches a forged completion. -/
inductive LocalTyped : Resource → LocalAction → Resource → Prop where
  | owner (none : resource.request = none) (fresh : op.fresh resource.nextSlot)
      (typing : Typed resource.cell op.lower next) :
      LocalTyped resource (.owner op)
        { resource with cell := next, nextSlot := op.advance resource.nextSlot }
  | submit (none : resource.request = none) (positive : 0 < length)
      (bounded : length ≤ resource.capacity) (typing : Typed resource.cell (.submit owner) next) :
      LocalTyped resource (.submit owner device queue descriptor queueEpoch length)
        { resource with
          cell := next
          request := some (submitted resource owner device queue descriptor queueEpoch length)
          serial := resource.serial + 1 }
  | reclaim (current : resource.request = some request)
      (capability : HasCapability resource.cell owner (.owner .pending))
      (boundOwner : owner = request.ownerSlot)
      (boundGeneration : resource.cell.generation = request.cellGeneration)
      (matching : Dma.Matches request completion) :
      LocalTyped resource (.reclaim owner completion)
        { resource with
          cell := liveCell resource.cell.owners resource.cell.borrows .cpu resource.cell.generation
          request := none }
  | retire (typing : Typed resource.cell (.retire owner) next) :
      LocalTyped resource (.retire owner) { resource with cell := next }

theorem local_progress (typing : LocalTyped resource action next) :
    resourceEval resource action = some next := by
  cases typing with
  | owner none fresh typed => simp [resourceEval, none, fresh, typed_progress typed]
  | submit none positive bounded typed =>
    simp [resourceEval, none, positive, bounded, typed_progress typed]
  | reclaim current capability boundOwner boundGeneration matching =>
    simp [resourceEval, current, Dma.reclaim, boundOwner, boundGeneration, matching,
      eval, HasCapability] at *
    simp_all
  | retire typed => simp [resourceEval, typed_progress typed]

theorem local_preservation (valid : Valid resource) (typing : LocalTyped resource action next) :
    Valid next := by
  cases typing with
  | owner none fresh typed =>
    refine ⟨typed_preservation valid.1 typed,
      eval_preserves_unique valid.2.1 (typed_progress typed), ?_,
      owner_slots_below valid.2.2.2 fresh typed⟩
    rcases owner_result_cpu typed with ⟨cpu, ordinary⟩
    simp [RequestCoherent, none, cpu, ordinary]
  | submit none positive bounded typed =>
    refine ⟨typed_preservation valid.1 typed,
      eval_preserves_unique valid.2.1 (typed_progress typed), ?_, ?_⟩
    · cases typed with
      | submit source unique noLoans =>
        constructor
        · simp [RequestBound, submitted, liveCell, positive, bounded]
        · exact .inr ⟨rfl, rfl, source.2.2⟩
    · cases typed with
      | submit source unique noLoans =>
        simpa [SlotsBelow, Active, liveCell, noLoans] using valid.2.2.2
  | reclaim current capability boundOwner boundGeneration matching =>
    exact ⟨live_wellFormed _ _ _ (valid.1.1.mp capability.1), valid.2.1,
      by simp [RequestCoherent, liveCell], valid.2.2.2⟩
  | retire typed =>
    refine ⟨typed_preservation valid.1 typed,
      eval_preserves_unique valid.2.1 (typed_progress typed), ?_, ?_⟩
    · cases typed with
      | retire source unique noLoans =>
        rcases pending_current_request valid source.1 source.2.1 with
          ⟨request, current, bound, owner⟩
        simp only [RequestCoherent, current]
        exact ⟨by simpa [RequestBound, quarantinedCell] using bound, .inl rfl⟩
    · cases typed
      simp [SlotsBelow, Active, quarantinedCell, has]

theorem local_request_origin (typing : LocalTyped resource action next)
    (current : next.request = some request) :
    resource.request = some request ∨ AddsQueue action request.queue := by
  cases typing with
  | owner none fresh typed => simp [none] at current
  | submit none positive bounded typed =>
    cases current
    exact .inr rfl
  | reclaim saved capability boundOwner boundGeneration matching => simp at current
  | retire typed => exact .inl current

theorem local_dead_preserved (dead : DeadSlot resource slot)
    (typing : LocalTyped resource action next) : DeadSlot next slot := by
  cases typing with
  | owner none fresh typed => exact owner_dead_preserved dead fresh typed
  | submit none positive bounded typed =>
    cases typed with
    | submit capability unique noLoans =>
      refine ⟨dead.1, ?_⟩
      intro active
      apply dead.2
      rcases active with owned | borrowed
      · exact .inl owned
      · simp [liveCell, has] at borrowed
  | reclaim current capability boundOwner boundGeneration matching => exact dead
  | retire typed =>
    cases typed
    exact ⟨dead.1, by simp [Active, quarantinedCell, has]⟩

theorem move_marks_dead (valid : Valid resource)
    (typing : LocalTyped resource (.owner (.move source target scope)) next) :
    DeadSlot next source := by
  cases typing with
  | owner none fresh typed =>
    cases typed with
    | move capability unused =>
      have below := valid.2.2.2 source (.inl capability.2.2)
      have lower : resource.nextSlot ≤ target := fresh
      have different : target ≠ source := by omega
      refine ⟨by simp only [OwnerOp.advance]; omega, ?_⟩
      intro active
      rcases active_new_owner active with same | old
      · exact different same
      · rcases old with owned | borrowed
        · exact moved_source_absent _ _ owned
        · exact owner_not_borrowed valid.2.1 capability.2.2 borrowed

theorem end_borrow_marks_dead (valid : Valid resource)
    (typing : LocalTyped resource (.owner (.endBorrow slot)) next) : DeadSlot next slot := by
  cases typing with
  | owner none fresh typed =>
    cases typed with
    | endBorrow capability =>
      refine ⟨valid.2.2.2 slot (.inr capability.2.2), ?_⟩
      intro active
      rcases active with owned | borrowed
      · exact owner_not_borrowed valid.2.1 owned capability.2.2
      · exact moved_source_absent _ _ borrowed

theorem release_marks_dead (valid : Valid resource)
    (typing : LocalTyped resource (.owner (.release slot)) next) : DeadSlot next slot := by
  cases typing with
  | owner none fresh typed =>
    cases typed with
    | release capability safe =>
      refine ⟨valid.2.2.2 slot (.inl capability.2.2), ?_⟩
      intro active
      rcases cleanup_active active with owned | borrowed
      · exact moved_source_absent _ _ owned
      · exact owner_not_borrowed valid.2.1 capability.2.2 borrowed

theorem reuse_marks_dead (valid : Valid resource)
    (typing : LocalTyped resource (.owner (.reuse source target scope)) next) :
    DeadSlot next source := by
  cases typing with
  | owner none fresh typed =>
    cases typed with
    | reuse capability unused unique noLoans =>
      have below := valid.2.2.2 source (.inl capability.2.2)
      have lower : resource.nextSlot ≤ target := fresh
      have different : target ≠ source := by omega
      refine ⟨by simp only [OwnerOp.advance]; omega, ?_⟩
      intro active
      rcases active_new_owner active with same | old
      · exact different same
      · simp [has] at old

theorem canonical_reclaim_origin (valid : Valid resource)
    (executed : resourceEval resource (.reclaim owner completion) = some next) :
    ∃ request, resource.request = some request ∧ RequestBound resource request ∧
      owner = request.ownerSlot ∧ resource.cell.generation = request.cellGeneration ∧
      Dma.Matches request completion ∧ next.request = none := by
  cases current : resource.request with
  | none => simp [resourceEval, current] at executed
  | some request =>
    have coherent := valid.2.2.1
    simp only [RequestCoherent, current] at coherent
    cases computed : Dma.reclaim resource.cell owner request completion with
    | none => simp [resourceEval, current, computed] at executed
    | some view =>
      simp [resourceEval, current, computed] at executed
      cases executed
      have guard := Dma.reclaim_guard computed
      exact ⟨request, rfl, coherent.1, guard.1, guard.2.1, guard.2.2, rfl⟩

def DeadAt (context : Context) (index slot : Nat) : Prop :=
  ∃ resource, context[index]? = some resource ∧ DeadSlot resource slot

theorem serial_dead_at (dead : DeadAt context index slot) (serial : Nat) :
    DeadAt (context.map fun resource => { resource with serial := serial }) index slot := by
  induction context generalizing index with
  | nil => rcases dead with ⟨resource, present, _⟩; simp at present
  | cons head rest ih =>
    cases index with
    | zero =>
      rcases dead with ⟨resource, present, absent⟩
      cases present
      exact ⟨_, rfl, absent⟩
    | succ index =>
      rcases dead with ⟨resource, present, absent⟩
      rcases ih (index := index) ⟨resource, present, absent⟩ with ⟨next, nextPresent, nextDead⟩
      exact ⟨next, nextPresent, nextDead⟩

theorem prepare_dead_at (dead : DeadAt context index slot) :
    DeadAt (prepare context action) index slot := by
  unfold prepare
  split
  · exact serial_dead_at dead _
  · exact dead

theorem append_dead_at (dead : DeadAt context index slot) (extra : Context) :
    DeadAt (context ++ extra) index slot := by
  induction context generalizing index with
  | nil => rcases dead with ⟨resource, present, _⟩; simp at present
  | cons head rest ih =>
    cases index with
    | zero => exact dead
    | succ index =>
      rcases dead with ⟨resource, present, absent⟩
      rcases ih (index := index) ⟨resource, present, absent⟩ with ⟨next, nextPresent, nextDead⟩
      exact ⟨next, nextPresent, nextDead⟩

theorem stale_request_rejected (current : resource.request = some request)
    (stale : completion.generation ≠ request.generation) :
    resourceEval resource (.reclaim owner completion) = none := by
  simp [resourceEval, current, Dma.stale_generation_rejected stale]

theorem forged_device_rejected (current : resource.request = some request)
    (wrong : completion.device ≠ request.device) :
    resourceEval resource (.reclaim owner completion) = none := by
  simp [resourceEval, current, Dma.mismatched_device_rejected wrong]

theorem no_request_rejected (absent : resource.request = none) :
    resourceEval resource (.reclaim owner completion) = none := by
  simp [resourceEval, absent]

theorem fresh_submit_rejects_old_completion {resource pending : Resource}
    {context : Context} {completion : Dma.Completion}
    (submittedNow : resourceEval { resource with serial := contextNonce context }
      (.submit owner device queue descriptor queueEpoch length) = some pending)
    (old : completion.generation ≤ contextNonce context) :
    resourceEval pending (.reclaim owner completion) = none := by
  simp only [resourceEval] at submittedNow
  split at submittedNow
  · cases computed : eval resource.cell (.submit owner) with
    | none => simp [computed] at submittedNow
    | some cell =>
      simp [computed] at submittedNow
      cases submittedNow
      apply stale_request_rejected (by rfl)
      simp only [submitted]
      omega
  · simp at submittedNow

theorem local_serial_order (typing : LocalTyped resource action next) :
    resource.serial ≤ next.serial := by
  cases typing <;> simp_all <;> omega

def updateAt (context : Context) (index : Nat) (action : LocalAction) : Option Context := do
  let resource ← context[index]?
  let next ← resourceEval resource action
  pure (context.set index next)

@[simp] theorem updateAt_zero : updateAt (resource :: rest) 0 action =
    (resourceEval resource action).map (· :: rest) := by
  cases computed : resourceEval resource action <;> simp [updateAt, computed, List.set]

@[simp] theorem updateAt_successor : updateAt (resource :: rest) (index + 1) action =
    (updateAt rest index action).map (resource :: ·) := by
  cases found : rest[index]? with
  | none => simp [updateAt, found]
  | some current =>
    cases computed : resourceEval current action <;> simp [updateAt, found, computed, List.set]

inductive AtTyped : Context → Nat → LocalAction → Context → Prop where
  | here : LocalTyped resource action next →
      AtTyped (resource :: rest) 0 action (next :: rest)
  | there : AtTyped rest index action next →
      AtTyped (resource :: rest) (index + 1) action (resource :: next)

theorem at_progress (typing : AtTyped context index action next) :
    updateAt context index action = some next := by
  induction typing with
  | here typed => simp [local_progress typed]
  | there typed ih => simp [ih]

theorem at_preservation (valid : ContextValid context)
    (typing : AtTyped context index action next) : ContextValid next := by
  induction typing with
  | here typed =>
    have head := local_preservation (valid _ (by simp)) typed
    intro resource member
    rcases List.mem_cons.mp member with eq | member
    · subst resource
      exact head
    · exact valid _ (by simp [member])
  | there typed ih =>
    have out := ih (fun resource member => valid resource (List.mem_cons_of_mem _ member))
    intro resource member
    rcases List.mem_cons.mp member with eq | member
    · subst resource
      exact valid _ (by simp)
    · exact out _ member

theorem at_request_origin (typing : AtTyped context index action next)
    (member : resource ∈ next) (current : resource.request = some request) :
    (∃ prior ∈ context, prior.request = some request) ∨ AddsQueue action request.queue := by
  induction typing generalizing resource request with
  | here typed =>
    rcases List.mem_cons.mp member with same | member
    · subst resource
      rcases local_request_origin typed current with old | added
      · exact .inl ⟨_, List.Mem.head _, old⟩
      · exact .inr added
    · exact .inl ⟨resource, List.mem_cons_of_mem _ member, current⟩
  | there typed ih =>
    rcases List.mem_cons.mp member with same | member
    · subst resource
      exact .inl ⟨_, List.Mem.head _, current⟩
    · rcases ih member current with ⟨prior, oldMember, oldCurrent⟩ | added
      · exact .inl ⟨prior, List.mem_cons_of_mem _ oldMember, oldCurrent⟩
      · exact .inr added

theorem at_queues_unique (unique : QueuesUnique context) (fresh : FreshQueues context action)
    (typing : AtTyped context index action next) : QueuesUnique next := by
  induction typing with
  | here typed =>
    rcases List.pairwise_cons.mp unique with ⟨apart, restUnique⟩
    apply List.pairwise_cons.mpr
    refine ⟨?_, restUnique⟩
    intro item member first second headCurrent itemCurrent
    rcases local_request_origin typed headCurrent with old | added
    · exact apart item member first second old itemCurrent
    · intro same
      exact fresh item (List.mem_cons_of_mem _ member) second itemCurrent (same ▸ added)
  | there typed ih =>
    rcases List.pairwise_cons.mp unique with ⟨apart, restUnique⟩
    apply List.pairwise_cons.mpr
    refine ⟨?_, ih restUnique (fun resource member request current =>
      fresh resource (List.mem_cons_of_mem _ member) request current)⟩
    intro item member first second headCurrent itemCurrent
    rcases at_request_origin typed member itemCurrent with ⟨prior, oldMember, oldCurrent⟩ | added
    · exact apart prior oldMember first second headCurrent oldCurrent
    · intro same
      exact fresh _ (List.Mem.head _) first headCurrent (same.symm ▸ added)

theorem at_dead_preserved (dead : DeadAt context staleIndex slot)
    (typing : AtTyped context index action next) : DeadAt next staleIndex slot := by
  induction typing generalizing staleIndex with
  | here typed =>
    cases staleIndex with
    | zero =>
      rcases dead with ⟨resource, present, absent⟩
      cases present
      exact ⟨_, rfl, local_dead_preserved absent typed⟩
    | succ staleIndex =>
      rcases dead with ⟨resource, present, absent⟩
      exact ⟨resource, present, absent⟩
  | there typed ih =>
    cases staleIndex with
    | zero => exact dead
    | succ staleIndex =>
      rcases dead with ⟨resource, present, absent⟩
      rcases ih (staleIndex := staleIndex) ⟨resource, present, absent⟩ with
        ⟨next, nextPresent, nextDead⟩
      exact ⟨next, nextPresent, nextDead⟩

theorem at_serial_order (typing : AtTyped context index action next) : SerialOrder context next := by
  induction typing with
  | here typed => exact .cons (local_serial_order typed) (serial_order_refl _)
  | there typed ih => exact .cons (Nat.le_refl _) ih

theorem at_submit_strict
    (typing : AtTyped context index (.submit owner device queue descriptor queueEpoch length) next)
    (floor : ∀ resource ∈ context, resource.serial = nonce) : nonce + 1 ≤ contextNonce next := by
  induction index generalizing context next with
  | zero =>
    cases typing with
    | here typed =>
      have head := floor _ (List.Mem.head _)
      cases typed
      simp only [contextNonce_cons, head]
      exact Nat.le_max_left _ _
  | succ index ih =>
    cases typing with
    | there typed =>
      have lower := ih typed
        (fun resource member => floor resource (List.mem_cons_of_mem _ member))
      simp only [contextNonce_cons]
      exact Nat.le_trans lower (Nat.le_max_right _ _)

/-- Concrete storage has independent payload and allocation bits. Consistency
    relates the typed resource context to that store, rather than assuming every
    arbitrary store starts in a safe state. Deferred physical work is accounted
    separately by the reclamation refinement. -/
structure Storage where
  allocated : Bool
  payload : Nat
  request : Option Dma.Request := none
  serial : Nat := 0
  nextSlot : Nat := 0
  deriving DecidableEq, Repr

abbrev Heap := Nat → Storage

def allocated (resource : Resource) : Bool :=
  decide (resource.cell.life = .live ∨ resource.cell.life = .quarantined)

def StoreConsistent (context : Context) (heap : Heap) : Prop :=
  (∀ index resource, context[index]? = some resource →
    (heap index).allocated = allocated resource ∧
    (heap index).request = resource.request ∧ (heap index).serial = resource.serial ∧
    (heap index).nextSlot = resource.nextSlot) ∧
  (∀ index, context[index]? = none → (heap index).allocated = false)

def syncStore (context : Context) (heap : Heap) : Heap := fun index =>
  match context[index]? with
  | none => { heap index with allocated := false, request := none, serial := 0, nextSlot := 0 }
  | some resource => { heap index with
      allocated := allocated resource
      request := resource.request
      serial := resource.serial
      nextSlot := resource.nextSlot }

theorem sync_consistent (context : Context) (heap : Heap) :
    StoreConsistent context (syncStore context heap) := by
  constructor
  · intro index resource present
    simp [syncStore, present]
  · intro index absent
    simp [syncStore, absent]

inductive Primitive where
  | scalar | mmio | signal | floating | blocking | lock | native | indirect | cyclic
  deriving DecidableEq, Repr

def Primitive.effect : Primitive → Effect
  | .scalar => .scalar
  | .mmio => .mmio
  | .signal => .signal
  | .floating => .float
  | .blocking => .blocking
  | .lock => .lock
  | .native => .native
  | .indirect => .indirect
  | .cyclic => .cyclic

inductive Action where
  | resource (index : Nat) (action : LocalAction)
  | allocate (owner scope capacity : Nat) (policy : Reclamation.Policy)
  | primitive (primitive : Primitive)
  | irqEnter | irqExit
  deriving DecidableEq, Repr

def Action.effect : Action → Effect
  | .resource .. | .allocate .. => .managed
  | .primitive prim => Primitive.effect prim
  | .irqEnter | .irqExit => .signal

structure State where
  context : Context
  heap : Heap
  inIrq : Bool := false

def State.nonce (state : State) : Nat := contextNonce state.context

def Consistent (context : Context) (state : State) : Prop :=
  state.context = context ∧ ContextValid context ∧ StoreConsistent context state.heap ∧
    QueuesUnique context

def step (state : State) : Action → Option State
  | .resource index action =>
    if state.inIrq then none else do
      if !queueAvailable state.context action then none else do
        let next ← updateAt (prepare state.context action) index action
        pure { state with context := next, heap := syncStore next state.heap }
  | .allocate owner scope capacity policy =>
    if state.inIrq then none else
    let resource : Resource := ⟨liveCell [⟨owner, scope⟩] [] .cpu 0, policy, capacity, none, 0, owner + 1⟩
    let next := state.context ++ [resource]
    some { state with context := next, heap := syncStore next state.heap }
  | .primitive primitive =>
    if state.inIrq then (if IrqSafe primitive.effect then some state else none) else some state
  | .irqEnter =>
    if state.inIrq then none else some { state with inIrq := true }
  | .irqExit =>
    if state.inIrq then some { state with inIrq := false } else none

inductive ActionTyped : Context → Bool → Action → Context → Bool → Prop where
  | resource (available : queueAvailable context action = true)
      (typing : AtTyped (prepare context action) index action next) :
      ActionTyped context false (.resource index action) next false
  | allocate : ActionTyped context false (.allocate owner scope capacity policy)
      (context ++ [⟨liveCell [⟨owner, scope⟩] [] .cpu 0, policy, capacity, none, 0, owner + 1⟩]) false
  | normalPrimitive : ActionTyped context false (.primitive primitive) context false
  | irqPrimitive (safe : IrqSafe primitive.effect) :
      ActionTyped context true (.primitive primitive) context true
  | enter : ActionTyped context false .irqEnter context true
  | leave : ActionTyped context true .irqExit context false

theorem action_type_soundness (consistent : Consistent context state)
    (irq : state.inIrq = mode) (typing : ActionTyped context mode action next nextMode) :
    ∃ result, step state action = some result ∧
      Consistent next result ∧ result.inIrq = nextMode := by
  rcases consistent with ⟨same, valid, store, queues⟩
  cases typing with
  | resource available typed =>
    let result : State := { state with context := next, heap := syncStore next state.heap }
    exact ⟨result, by simp [step, irq, same, available, at_progress typed, result],
      ⟨rfl, at_preservation (prepare_valid valid) typed, sync_consistent _ _,
        at_queues_unique (prepare_queues queues) (prepare_fresh available) typed⟩, irq⟩
  | @allocate owner scope capacity policy =>
    let resource : Resource := ⟨liveCell [⟨owner, scope⟩] [] .cpu 0, policy, capacity, none, 0, owner + 1⟩
    let out := context ++ [resource]
    refine ⟨{ state with context := out, heap := syncStore out state.heap }, ?_, ?_, irq⟩
    · simp [step, irq, same, out, resource]
    · refine ⟨rfl, ?_, sync_consistent _ _, queues_append_none queues rfl⟩
      intro item member
      rcases List.mem_append.mp member with old | fresh
      · exact valid item old
      · have eq : item = resource := by simpa using fresh
        subst item
        exact ⟨live_wellFormed _ _ _ (by simp),
          by simp [UniqueSlots, TokensUnique, resource, liveCell],
          by simp [RequestCoherent, resource, liveCell],
          by simp [SlotsBelow, Active, resource, liveCell, has]⟩
  | normalPrimitive => exact ⟨state, by simp [step, irq], ⟨same, valid, store, queues⟩, irq⟩
  | irqPrimitive safe => exact ⟨state, by simp [step, irq, safe], ⟨same, valid, store, queues⟩, irq⟩
  | enter => exact ⟨{ state with inIrq := true }, by simp [step, irq], ⟨same, valid, store, queues⟩, rfl⟩
  | leave => exact ⟨{ state with inIrq := false }, by simp [step, irq], ⟨same, valid, store, queues⟩, rfl⟩

theorem nonce_append (left right : Context) : contextNonce left ≤ contextNonce (left ++ right) := by
  induction left with
  | nil => exact Nat.zero_le _
  | cons head rest ih =>
    simp only [List.cons_append, contextNonce_cons]
    exact Nat.max_le_of_le_of_le (Nat.le_max_left _ _)
      (Nat.le_trans ih (Nat.le_max_right _ _))

theorem action_nonce_monotone (typing : ActionTyped context mode action next nextMode) :
    contextNonce context ≤ contextNonce next := by
  cases typing with
  | resource available typed =>
    exact Nat.le_trans (serial_order_nonce (prepare_order _ _))
      (serial_order_nonce (at_serial_order typed))
  | allocate => exact nonce_append _ _
  | normalPrimitive => exact Nat.le_refl _
  | irqPrimitive safe => exact Nat.le_refl _
  | enter => exact Nat.le_refl _
  | leave => exact Nat.le_refl _

theorem public_busy_queue_rejected (member : resource ∈ state.context)
    (current : resource.request = some request) (same : request.queue = queue) :
    step state (.resource index (.submit owner device queue descriptor queueEpoch length)) = none := by
  simp [step, busy_queue_unavailable member current same]

theorem quarantined_queue_poisoned (consistent : Consistent context state)
    (member : resource ∈ context) (quarantined : resource.cell.life = .quarantined) :
    ∃ request, resource.request = some request ∧ RequestBound resource request ∧
      ∀ index owner device descriptor queueEpoch length,
        step state (.resource index
          (.submit owner device request.queue descriptor queueEpoch length)) = none := by
  rcases quarantined_current_request (consistent.2.1 resource member) quarantined with
    ⟨request, current, bound⟩
  refine ⟨request, current, bound, ?_⟩
  intro index owner device descriptor queueEpoch length
  apply public_busy_queue_rejected (resource := resource) (request := request)
  · simpa [consistent.1] using member
  · exact current
  · rfl

theorem public_submit_nonce_strict
    (typing : ActionTyped context false
      (.resource index (.submit owner device queue descriptor queueEpoch length)) next false) :
    contextNonce context < contextNonce next := by
  cases typing with
  | resource available typed =>
    have lower := at_submit_strict typed (nonce := contextNonce context)
      (fun resource member => prepare_submit_floor member)
    exact Nat.lt_of_lt_of_le (Nat.lt_succ_self _) lower

inductive ProgramTyped : Context → Bool → List Action → Context → Bool → Prop where
  | nil : ProgramTyped context mode [] context mode
  | cons : ActionTyped context mode action next nextMode →
      ProgramTyped next nextMode rest result resultMode →
      ProgramTyped context mode (action :: rest) result resultMode

theorem action_dead_preserved (dead : DeadAt context index slot)
    (typing : ActionTyped context mode action next nextMode) : DeadAt next index slot := by
  cases typing with
  | resource available typed => exact at_dead_preserved (prepare_dead_at dead) typed
  | allocate => exact append_dead_at dead _
  | normalPrimitive => exact dead
  | irqPrimitive safe => exact dead
  | enter => exact dead
  | leave => exact dead

theorem program_dead_preserved (dead : DeadAt context index slot)
    (typing : ProgramTyped context mode program final finalMode) : DeadAt final index slot := by
  induction typing with
  | nil => exact dead
  | cons first rest ih => exact ih (action_dead_preserved dead first)

theorem stale_capability_never_returns (dead : DeadAt context index slot)
    (typing : ProgramTyped context mode program final finalMode) :
    ∃ resource, final[index]? = some resource ∧ DeadSlot resource slot ∧
      resourceEval resource (.owner (.use slot)) = none ∧
      resourceEval resource (.owner (.release slot)) = none := by
  rcases program_dead_preserved dead typing with ⟨resource, present, absent⟩
  have noOwner : ¬ has resource.cell.owners slot := fun owned => absent.2 (.inl owned)
  have noBorrow : ¬ has resource.cell.borrows slot := fun borrowed => absent.2 (.inr borrowed)
  exact ⟨resource, present, absent,
    by simp [resourceEval, OwnerOp.lower, OwnerOp.fresh, eval, noOwner, noBorrow],
    by simp [resourceEval, OwnerOp.lower, OwnerOp.fresh, eval, noOwner]⟩

theorem program_nonce_monotone (typing : ProgramTyped context mode program final finalMode) :
    contextNonce context ≤ contextNonce final := by
  induction typing with
  | nil => exact Nat.le_refl _
  | cons head tail ih => exact Nat.le_trans (action_nonce_monotone head) ih

/-- The historical nonce remains invalid after any intervening typed program,
    including reclaim, allocation and queue reuse by a different resource. -/
theorem historical_replay_rejected {resource pending : Resource}
    {completion : Dma.Completion}
    (first : ActionTyped before false
      (.resource oldIndex (.submit oldOwner oldDevice oldQueue oldDescriptor oldEpoch oldLength))
      after false)
    (history : ProgramTyped after false program current false)
    (fresh : resourceEval { resource with serial := contextNonce current }
      (.submit owner device queue descriptor queueEpoch length) = some pending)
    (old : completion.generation = contextNonce before + 1) :
    resourceEval pending (.reclaim owner completion) = none := by
  have advanced := public_submit_nonce_strict first
  have retained := program_nonce_monotone history
  apply fresh_submit_rejects_old_completion fresh
  omega

def run (state : State) (program : List Action) : Option State := program.foldlM step state

@[simp] theorem run_nil : run state [] = some state := rfl

@[simp] theorem run_cons : run state (action :: rest) =
    (step state action).bind (fun next => run next rest) := rfl

theorem public_type_soundness (consistent : Consistent context state)
    (irq : state.inIrq = mode) (typing : ProgramTyped context mode program final finalMode) :
    ∃ result, run state program = some result ∧ Consistent final result ∧ result.inIrq = finalMode := by
  induction typing generalizing state with
  | nil => exact ⟨state, rfl, consistent, irq⟩
  | cons typed rest ih =>
    rcases action_type_soundness consistent irq typed with ⟨next, head, nextConsistent, nextIrq⟩
    rcases ih nextConsistent nextIrq with ⟨result, tail, finalConsistent, finalIrq⟩
    exact ⟨result, by simp [run_cons, head, tail], finalConsistent, finalIrq⟩

theorem public_context_coherence (consistent : Consistent context state)
    (irq : state.inIrq = mode) (typing : ProgramTyped context mode program final finalMode) :
    ∃ result, run state program = some result ∧ ContextValid final ∧ QueuesUnique final ∧
      ∀ resource ∈ final, RequestCoherent resource := by
  rcases public_type_soundness consistent irq typing with
    ⟨result, execution, finalConsistent, finalIrq⟩
  exact ⟨result, execution, finalConsistent.2.1, finalConsistent.2.2.2,
    fun resource member => (finalConsistent.2.1 resource member).2.2.1⟩

theorem public_read_allocated (consistent : Consistent context state)
    (present : context[index]? = some resource)
    (typed : LocalTyped resource (.owner (.use slot)) next) :
    (state.heap index).allocated = true := by
  have used := local_progress typed
  simp only [resourceEval] at used
  split at used
  · have core : eval resource.cell (.use slot) ≠ none := by
      intro absent
      simp [OwnerOp.lower, absent] at used
    cases computed : eval resource.cell (.use slot) with
    | none => exact False.elim (core computed)
    | some value =>
      have live := (use_valid computed).1
      rw [(consistent.2.2.1.1 index resource present).1]
      simp [allocated, live]
  · simp at used

theorem closed_store_only_quarantine (consistent : Consistent context state)
    (closed : ContextClosed context) :
    ∀ index, (state.heap index).allocated = true →
      ∃ resource, context[index]? = some resource ∧ resource.cell.life = .quarantined := by
  intro index live
  cases present : context[index]? with
  | none =>
    have absent := consistent.2.2.1.2 index present
    simp [live] at absent
  | some resource =>
    have member : resource ∈ context := (List.mem_iff_getElem?).mpr ⟨index, present⟩
    have notLive := (closed resource member).2.2
    have bit := (consistent.2.2.1.1 index resource present).1
    have status : resource.cell.life = .live ∨ resource.cell.life = .quarantined := by
      simpa [allocated] using bit.symm.trans live
    exact ⟨resource, rfl, status.resolve_left notLive⟩

/-- Final-context cleanup composes program soundness with the finite scope
    theorem. The final ownership context must actually be local to the exit. -/
theorem program_scope_cleanup (consistent : Consistent context state)
    (irq : state.inIrq = false) (typing : ProgramTyped context false program final false)
    (ready : ContextLocal scope final) (ledger : Reclamation.Ledger) :
    ∃ result exited closed debt, run state program = some result ∧ Consistent final result ∧
      closeContext scope final ledger = some (closed, debt) ∧ ContextClosed closed ∧
      Consistent closed exited ∧
      (∀ index, (exited.heap index).allocated = true →
        ∃ resource, closed[index]? = some resource ∧ resource.cell.life = .quarantined) ∧
      ∀ budget, debt.queued ≤ budget →
        Reclamation.outstanding (Reclamation.poll debt budget) + pinnedCount closed =
          debt.cycles + pinnedCount final := by
  rcases public_type_soundness consistent irq typing with ⟨result, run, resultConsistent, mode⟩
  rcases finite_scope_cleanup ready ledger with
    ⟨closed, debt, cleanup, valid, noOwners, pinned, accounting⟩
  let exited : State := { result with context := closed, heap := syncStore closed result.heap }
  have exitedConsistent : Consistent closed exited := ⟨rfl, valid, sync_consistent _ _,
    close_context_queues_unique resultConsistent.2.2.2 cleanup⟩
  refine ⟨result, exited, closed, debt, run, resultConsistent, cleanup, noOwners,
    exitedConsistent, closed_store_only_quarantine exitedConsistent noOwners, ?_⟩
  intro budget enough
  rw [Reclamation.drain_modulo_cycles debt enough, pinned]

end Minyar.Language
