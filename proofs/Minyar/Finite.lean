import Minyar.Uniqueness
import Minyar.Reclamation
import Minyar.Dma

namespace Minyar.Finite

structure Resource where
  cell : Cell
  policy : Reclamation.Policy
  capacity : Nat := 1
  request : Option Dma.Request := none
  serial : Nat := 0
  nextSlot : Nat := 0
  deriving DecidableEq, Repr

abbrev Context := List Resource

/-- Saved DMA metadata is tied to its actual allocation and persistent serial. -/
def RequestBound (resource : Resource) (request : Dma.Request) : Prop :=
  request.cellGeneration = resource.cell.generation ∧ request.capacity = resource.capacity ∧
  0 < request.submitted ∧ request.submitted ≤ resource.capacity ∧
  0 < request.generation ∧ request.generation ≤ resource.serial

def RequestCoherent (resource : Resource) : Prop :=
  match resource.request with
  | none => resource.cell.life ≠ .quarantined ∧
      ¬ (resource.cell.life = .live ∧ resource.cell.phase = .pending)
  | some request => RequestBound resource request ∧
      (resource.cell.life = .quarantined ∨
        (resource.cell.life = .live ∧ resource.cell.phase = .pending ∧
          has resource.cell.owners request.ownerSlot))

def Active (cell : Cell) (slot : Nat) : Prop :=
  has cell.owners slot ∨ has cell.borrows slot

def SlotsBelow (cell : Cell) (nextSlot : Nat) : Prop :=
  ∀ slot, Active cell slot → slot < nextSlot

def DeadSlot (resource : Resource) (slot : Nat) : Prop :=
  slot < resource.nextSlot ∧ ¬ Active resource.cell slot

def Valid (resource : Resource) : Prop :=
  WellFormed resource.cell ∧ UniqueSlots resource.cell ∧ RequestCoherent resource ∧
    SlotsBelow resource.cell resource.nextSlot

def ContextValid (context : Context) : Prop := ∀ resource ∈ context, Valid resource

theorem request_bound_raise (bound : RequestBound resource request)
    (higher : resource.serial ≤ serial) : RequestBound { resource with serial := serial } request := by
  rcases bound with ⟨generation, capacity, positive, bounded, nonce, serialBound⟩
  exact ⟨generation, capacity, positive, bounded, nonce, Nat.le_trans serialBound higher⟩

theorem request_coherent_raise (coherent : RequestCoherent resource)
    (higher : resource.serial ≤ serial) : RequestCoherent { resource with serial := serial } := by
  cases current : resource.request with
  | none => simpa [RequestCoherent, current] using coherent
  | some request =>
    simp only [RequestCoherent, current] at coherent ⊢
    exact ⟨request_bound_raise coherent.1 higher, coherent.2⟩

theorem pending_current_request (valid : Valid resource)
    (live : resource.cell.life = .live) (pending : resource.cell.phase = .pending) :
    ∃ request, resource.request = some request ∧ RequestBound resource request ∧
      has resource.cell.owners request.ownerSlot := by
  have coherent := valid.2.2.1
  cases current : resource.request with
  | none => simp [RequestCoherent, current, live, pending] at coherent
  | some request =>
    simp only [RequestCoherent, current] at coherent
    refine ⟨request, rfl, coherent.1, ?_⟩
    rcases coherent.2 with quarantined | active
    · simp [live] at quarantined
    · exact active.2.2

theorem quarantined_current_request (valid : Valid resource)
    (quarantined : resource.cell.life = .quarantined) :
    ∃ request, resource.request = some request ∧ RequestBound resource request := by
  have coherent := valid.2.2.1
  cases current : resource.request with
  | none => simp [RequestCoherent, current, quarantined] at coherent
  | some request =>
    simp only [RequestCoherent, current] at coherent
    exact ⟨request, rfl, coherent.1⟩

theorem cpu_request_none (valid : Valid resource)
    (ordinary : resource.cell.life ≠ .quarantined) (cpu : resource.cell.phase = .cpu) :
    resource.request = none := by
  have coherent := valid.2.2.1
  cases current : resource.request with
  | none => rfl
  | some request => simp [RequestCoherent, current, ordinary, cpu] at coherent

def QueueApart (left right : Resource) : Prop :=
  ∀ first second, left.request = some first → right.request = some second →
    first.queue ≠ second.queue

def QueuesUnique (context : Context) : Prop := context.Pairwise QueueApart

def RequestSubset (next original : Resource) : Prop :=
  ∀ request, next.request = some request → original.request = some request

inductive RequestShrink : Context → Context → Prop where
  | nil : RequestShrink [] []
  | cons : RequestSubset next original → RequestShrink tail rest →
      RequestShrink (next :: tail) (original :: rest)

theorem request_shrink_refl (context : Context) : RequestShrink context context := by
  induction context with
  | nil => exact .nil
  | cons head rest ih => exact .cons (fun _ current => current) ih

theorem request_shrink_member (shrink : RequestShrink next original)
    (member : resource ∈ next) (current : resource.request = some request) :
    ∃ prior ∈ original, prior.request = some request := by
  induction shrink generalizing resource request with
  | nil => simp at member
  | @cons head prior tail rest subset shrink ih =>
    rcases List.mem_cons.mp member with same | member
    · subst resource
      exact ⟨prior, by simp, subset request current⟩
    · rcases ih member current with ⟨prior, member, current⟩
      exact ⟨prior, by simp [member], current⟩

theorem queues_shrink (unique : QueuesUnique original)
    (shrink : RequestShrink next original) : QueuesUnique next := by
  induction shrink with
  | nil => exact .nil
  | @cons head prior tail rest subset shrink ih =>
    rcases List.pairwise_cons.mp unique with ⟨apart, restUnique⟩
    apply List.pairwise_cons.mpr
    refine ⟨?_, ih restUnique⟩
    intro item member first second headCurrent itemCurrent
    rcases request_shrink_member shrink member itemCurrent with ⟨old, oldMember, oldCurrent⟩
    exact apart old oldMember first second (subset first headCurrent) oldCurrent

theorem queues_append_none (unique : QueuesUnique context) (absent : resource.request = none) :
    QueuesUnique (context ++ [resource]) := by
  induction context with
  | nil => simp [QueuesUnique]
  | cons head rest ih =>
    rcases List.pairwise_cons.mp unique with ⟨apart, restUnique⟩
    apply List.pairwise_cons.mpr
    refine ⟨?_, ih restUnique⟩
    intro item member first second headCurrent itemCurrent
    rcases List.mem_append.mp member with old | fresh
    · exact apart item old first second headCurrent itemCurrent
    · have same : item = resource := by simpa using fresh
      subst item
      simp [absent] at itemCurrent

def Closed (resource : Resource) : Prop :=
  resource.cell.owners = [] ∧ resource.cell.borrows = [] ∧ resource.cell.life ≠ .live

def ContextClosed (context : Context) : Prop := ∀ resource ∈ context, Closed resource

def Local (scope : Nat) (resource : Resource) : Prop :=
  Valid resource ∧ (resource.cell.life = .live →
    resource.cell.phase = .cpu ∧
    (∀ token ∈ resource.cell.owners, token.scope = scope) ∧
    (∀ token ∈ resource.cell.borrows, token.scope = scope))

def ContextLocal (scope : Nat) (context : Context) : Prop :=
  ∀ resource ∈ context, Local scope resource

def liveCount (context : Context) : Nat :=
  context.foldr (fun resource total => (if resource.cell.life = .live then 1 else 0) + total) 0

def pinnedCount (context : Context) : Nat :=
  context.foldr (fun resource total => (if resource.cell.life = .quarantined then 1 else 0) + total) 0

@[simp] theorem liveCount_cons : liveCount (resource :: rest) =
    (if resource.cell.life = .live then 1 else 0) + liveCount rest := rfl

@[simp] theorem pinnedCount_cons : pinnedCount (resource :: rest) =
    (if resource.cell.life = .quarantined then 1 else 0) + pinnedCount rest := rfl

def closeResource (scope : Nat) (resource : Resource) : Option Resource :=
  if resource.cell.life = .live then
    (eval resource.cell (.exit scope)).map fun next => { resource with cell := next, request := none }
  else some resource

theorem nonlive_closed (wf : WellFormed cell) (notLive : cell.life ≠ .live) :
    cell.owners = [] ∧ cell.borrows = [] ∧ cell.life ≠ .live := by
  have owners : cell.owners = [] := by
    by_cases empty : cell.owners = []
    · exact empty
    · exact False.elim (notLive (wf.1.mpr empty))
  exact ⟨owners, wf.2.1 notLive, notLive⟩

theorem close_resource_sound (ready : Local scope resource) :
    ∃ next, closeResource scope resource = some next ∧ Valid next ∧ Closed next ∧
      (if next.cell.life = .quarantined then 1 else 0) =
      (if resource.cell.life = .quarantined then 1 else 0) := by
  by_cases live : resource.cell.life = .live
  · have conditions := ready.2 live
    let next : Resource := { resource with cell := freedCell resource.cell.generation, request := none }
    refine ⟨next, ?_, ?_, ?_, ?_⟩
    · simp [closeResource, live, scope_no_leak live conditions.1 conditions.2.1 conditions.2.2, next]
    · exact ⟨freed_wellFormed _, by simp [UniqueSlots, TokensUnique, next, freedCell],
        by simp [RequestCoherent, next, freedCell],
        by simp [SlotsBelow, Active, next, freedCell, has]⟩
    · simp [Closed, next, freedCell]
    · simp [next, freedCell, live]
  · refine ⟨resource, ?_, ready.1, ?_, rfl⟩
    · simp [closeResource, live]
    · exact nonlive_closed ready.1.1 live

/-- Every logically released finite component contributes one explicit resource
    obligation. Refining that unit to C destructor/edge work is a separate proof. -/
def closeContext (scope : Nat) (context : Context) (ledger : Reclamation.Ledger) :
    Option (Context × Reclamation.Ledger) :=
  (context.foldr (fun resource continuation current => do
      let next ← closeResource scope resource
      let charged := if resource.cell.life = .live then
        Reclamation.retire current resource.policy 1 else current
      let (closed, final) ← continuation charged
      pure (next :: closed, final)) (fun current => some ([], current))) ledger

@[simp] theorem closeContext_cons : closeContext scope (resource :: rest) ledger = (do
    let next ← closeResource scope resource
    let charged := if resource.cell.life = .live then
      Reclamation.retire ledger resource.policy 1 else ledger
    let (closed, final) ← closeContext scope rest charged
    pure (next :: closed, final)) := rfl

theorem close_resource_request_subset (closed : closeResource scope resource = some next) :
    RequestSubset next resource := by
  unfold closeResource at closed
  split at closed
  · cases computed : eval resource.cell (.exit scope) with
    | none => simp [computed] at closed
    | some cell =>
      simp [computed] at closed
      cases closed
      intro request current
      simp at current
  · cases closed
    exact fun _ current => current

theorem close_context_request_shrink
    (closed : closeContext scope context ledger = some (next, final)) :
    RequestShrink next context := by
  induction context generalizing ledger next final with
  | nil =>
    have same : ([], ledger) = (next, final) := by simpa [closeContext] using closed
    cases same
    exact .nil
  | cons resource rest ih =>
    rw [closeContext_cons] at closed
    cases first : closeResource scope resource with
    | none => simp [first] at closed
    | some head =>
      let charged := if resource.cell.life = .live then
        Reclamation.retire ledger resource.policy 1 else ledger
      cases tail : closeContext scope rest charged with
      | none => simp [first, charged, tail] at closed
      | some pair =>
        rcases pair with ⟨out, debt⟩
        have same : (head :: out, debt) = (next, final) := by
          simpa [first, charged, tail] using closed
        cases same
        exact .cons (close_resource_request_subset first) (ih tail)

theorem close_context_queues_unique (unique : QueuesUnique context)
    (closed : closeContext scope context ledger = some (next, final)) : QueuesUnique next :=
  queues_shrink unique (close_context_request_shrink closed)

theorem finite_scope_cleanup (ready : ContextLocal scope context) (ledger : Reclamation.Ledger) :
    ∃ closed final, closeContext scope context ledger = some (closed, final) ∧
      ContextValid closed ∧ ContextClosed closed ∧
      pinnedCount closed = pinnedCount context ∧
      Reclamation.accounted final = Reclamation.accounted ledger + liveCount context := by
  induction context generalizing ledger with
  | nil =>
    exact ⟨[], ledger, rfl, by simp [ContextValid], by simp [ContextClosed], rfl, by simp [liveCount]⟩
  | cons resource rest ih =>
    have head := ready resource (by simp)
    have tail : ContextLocal scope rest := by
      intro item member
      exact ready item (by simp [member])
    rcases close_resource_sound head with ⟨next, step, valid, closed, pinned⟩
    let charged := if resource.cell.life = .live then
      Reclamation.retire ledger resource.policy 1 else ledger
    rcases ih tail charged with ⟨out, final, restStep, outValid, outClosed, outPinned, accounting⟩
    refine ⟨next :: out, final, ?_, ?_, ?_, ?_, ?_⟩
    · simp [closeContext_cons, step, charged, restStep]
    · intro item member
      rcases List.mem_cons.mp member with eq | member
      · subst item
        exact valid
      · exact outValid item member
    · intro item member
      rcases List.mem_cons.mp member with eq | member
      · subst item
        exact closed
      · exact outClosed item member
    · simp only [pinnedCount_cons, pinned, outPinned]
    · rw [accounting]
      by_cases live : resource.cell.life = .live
      · simp [charged, live, Reclamation.retire_accounts, liveCount]
        omega
      · simp [charged, live, liveCount]

/-- Closed context plus enough finite polling leaves only the stated cycle debt
    and intentionally pinned DMA resources. No unaccounted local owner remains. -/
theorem scope_no_leak_modulo_policy (ready : ContextLocal scope context)
    (ledger : Reclamation.Ledger) :
    ∃ closed final, closeContext scope context ledger = some (closed, final) ∧
      ContextClosed closed ∧
      Reclamation.accounted final = Reclamation.accounted ledger + liveCount context ∧
      ∀ budget, final.queued ≤ budget →
        Reclamation.outstanding (Reclamation.poll final budget) + pinnedCount closed =
          final.cycles + pinnedCount context := by
  rcases finite_scope_cleanup ready ledger with
    ⟨closed, final, step, valid, noOwners, pinned, accounting⟩
  exact ⟨closed, final, step, noOwners, accounting, fun budget enough => by
    rw [Reclamation.drain_modulo_cycles final enough, pinned]⟩

end Minyar.Finite
