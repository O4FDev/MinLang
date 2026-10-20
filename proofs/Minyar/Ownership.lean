import Std

/-! An executable resource calculus, not a model of the entire compiler or C ABI.
    Object identities are fresh allocation incarnations, not reusable addresses.
    Owners and borrows are explicit slots; scope exit removes a scope's slots.
    Each successful transition is decided by operational guards, never by testing
    WellFormed. The preservation proof below derives that invariant. -/

namespace Minyar

inductive Lifetime where
  | fresh | live | freed | quarantined
  deriving DecidableEq, Repr

inductive Phase where
  | cpu | pending
  deriving DecidableEq, Repr

structure Token where
  slot : Nat
  scope : Nat
  deriving DecidableEq, Repr

structure Cell where
  life : Lifetime := .fresh
  owners : List Token := []
  borrows : List Token := []
  phase : Phase := .cpu
  frees : Nat := 0
  generation : Nat := 0
  deriving DecidableEq, Repr

def initialCell : Cell := {}

def liveCell (owners borrows : List Token) (phase : Phase) (generation : Nat) : Cell :=
  ⟨.live, owners, borrows, phase, 0, generation⟩

def freedCell (generation : Nat) : Cell :=
  ⟨.freed, [], [], .cpu, 1, generation⟩

/-- The affine handle is gone; physical DMA backing remains intentionally pinned. -/
def quarantinedCell (generation : Nat) : Cell :=
  ⟨.quarantined, [], [], .cpu, 0, generation⟩

def has (tokens : List Token) (slot : Nat) : Prop :=
  ∃ token ∈ tokens, token.slot = slot

instance (tokens : List Token) (slot : Nat) : Decidable (has tokens slot) :=
  inferInstanceAs (Decidable (∃ token ∈ tokens, token.slot = slot))

def unused (c : Cell) (slot : Nat) : Prop :=
  ¬ has c.owners slot ∧ ¬ has c.borrows slot

instance (c : Cell) (slot : Nat) : Decidable (unused c slot) :=
  inferInstanceAs (Decidable (¬ has c.owners slot ∧ ¬ has c.borrows slot))

def withoutSlot (tokens : List Token) (slot : Nat) : List Token :=
  tokens.filter fun token => token.slot != slot

def withoutScope (tokens : List Token) (scope : Nat) : List Token :=
  tokens.filter fun token => token.scope != scope

inductive Op where
  | alloc (slot scope : Nat)
  | retain (source target scope : Nat)
  | move (source target scope : Nat)
  | borrow (source target scope : Nat)
  | endBorrow (slot : Nat)
  | use (slot : Nat)
  | release (slot : Nat)
  | reuse (source target scope : Nat)
  | exit (scope : Nat)
  | submit (slot : Nat)
  | complete (slot : Nat)
  | retire (slot : Nat)
  deriving DecidableEq, Repr

/-- The last-owner release guard is local: a loan cannot outlive all owners.
    Pending DMA is excluded by callers, before entering this cleanup primitive. -/
def cleanup (owners borrows : List Token) (generation : Nat) : Option Cell :=
  if owners = [] then
    if borrows = [] then some (freedCell generation) else none
  else some (liveCell owners borrows .cpu generation)

def eval (c : Cell) : Op → Option Cell
  | .alloc slot scope =>
    if c.life = .fresh then some (liveCell [⟨slot, scope⟩] [] .cpu 0) else none
  | .retain source target scope =>
    if c.life = .live ∧ c.phase = .cpu ∧ has c.owners source ∧ unused c target then
      some (liveCell (⟨target, scope⟩ :: c.owners) c.borrows .cpu c.generation)
    else none
  | .move source target scope =>
    if c.life = .live ∧ c.phase = .cpu ∧ has c.owners source ∧ unused c target then
      some (liveCell (⟨target, scope⟩ :: withoutSlot c.owners source)
        c.borrows .cpu c.generation)
    else none
  | .borrow source target scope =>
    if c.life = .live ∧ c.phase = .cpu ∧ has c.owners source ∧ unused c target then
      some (liveCell c.owners (⟨target, scope⟩ :: c.borrows) .cpu c.generation)
    else none
  | .endBorrow slot =>
    if c.life = .live ∧ c.phase = .cpu ∧ has c.borrows slot then
      some (liveCell c.owners (withoutSlot c.borrows slot) .cpu c.generation)
    else none
  | .use slot =>
    if c.life = .live ∧ c.phase = .cpu ∧ (has c.owners slot ∨ has c.borrows slot)
    then some c else none
  | .release slot =>
    if c.life = .live ∧ c.phase = .cpu ∧ has c.owners slot then
      cleanup (withoutSlot c.owners slot) c.borrows c.generation
    else none
  | .reuse source target scope =>
    if c.life = .live ∧ c.phase = .cpu ∧ has c.owners source ∧
        c.owners.length = 1 ∧ c.borrows = [] ∧ unused c target then
      some (liveCell [⟨target, scope⟩] [] .cpu (c.generation + 1))
    else none
  | .exit scope =>
    if c.life = .live ∧ c.phase = .cpu then
      cleanup (withoutScope c.owners scope) (withoutScope c.borrows scope) c.generation
    else none
  | .submit slot =>
    if c.life = .live ∧ c.phase = .cpu ∧ has c.owners slot ∧
        c.owners.length = 1 ∧ c.borrows = [] then
      some (liveCell c.owners [] .pending c.generation)
    else none
  | .complete slot =>
    if c.life = .live ∧ c.phase = .pending ∧ has c.owners slot then
      some (liveCell c.owners c.borrows .cpu c.generation)
    else none
  | .retire slot =>
    if c.life = .live ∧ c.phase = .pending ∧ has c.owners slot ∧
        c.owners.length = 1 ∧ c.borrows = [] then
      some (quarantinedCell c.generation)
    else none

def WellFormed (c : Cell) : Prop :=
  (c.life = .live ↔ c.owners ≠ []) ∧
  (c.life ≠ .live → c.borrows = []) ∧
  (c.phase = .pending → c.life = .live ∧ c.owners.length = 1 ∧ c.borrows = []) ∧
  c.frees = (if c.life = .freed then 1 else 0)

theorem initial_wellFormed : WellFormed initialCell := by
  simp [WellFormed, initialCell]

theorem live_wellFormed (owners borrows : List Token) (generation : Nat)
    (h : owners ≠ []) : WellFormed (liveCell owners borrows .cpu generation) := by
  simp [WellFormed, liveCell, h]

theorem freed_wellFormed (generation : Nat) : WellFormed (freedCell generation) := by
  simp [WellFormed, freedCell]

theorem quarantined_wellFormed (generation : Nat) :
    WellFormed (quarantinedCell generation) := by
  simp [WellFormed, quarantinedCell]

theorem cleanup_preserves (owners borrows : List Token) (generation : Nat)
    (h : cleanup owners borrows generation = some result) : WellFormed result := by
  unfold cleanup at h
  split at h
  · split at h
    · cases h
      exact freed_wellFormed generation
    · simp at h
  · rename_i nonempty
    cases h
    exact live_wellFormed owners borrows generation nonempty

/-- Preservation is proved from slot/phase guards, not assumed by eval. -/
theorem eval_preserves (wf : WellFormed c) (h : eval c op = some result) :
    WellFormed result := by
  have nonempty : c.life = .live → c.owners ≠ [] := wf.1.mp
  cases op with
  | alloc slot scope =>
    simp only [eval] at h
    split at h
    · cases h
      exact live_wellFormed _ _ _ (by simp)
    · simp at h
  | retain source target scope =>
    simp only [eval] at h
    split at h
    · cases h
      exact live_wellFormed _ _ _ (by simp)
    · simp at h
  | move source target scope =>
    simp only [eval] at h
    split at h
    · cases h
      exact live_wellFormed _ _ _ (by simp)
    · simp at h
  | borrow source target scope =>
    simp only [eval] at h
    split at h
    · rename_i guard
      cases h
      exact live_wellFormed _ _ _ (nonempty guard.1)
    · simp at h
  | endBorrow slot =>
    simp only [eval] at h
    split at h
    · rename_i guard
      cases h
      exact live_wellFormed _ _ _ (nonempty guard.1)
    · simp at h
  | use slot =>
    simp only [eval] at h
    split at h
    · cases h
      exact wf
    · simp at h
  | release slot =>
    simp only [eval] at h
    split at h
    · exact cleanup_preserves _ _ _ h
    · simp at h
  | reuse source target scope =>
    simp only [eval] at h
    split at h
    · cases h
      exact live_wellFormed _ _ _ (by simp)
    · simp at h
  | exit scope =>
    simp only [eval] at h
    split at h
    · exact cleanup_preserves _ _ _ h
    · simp at h
  | submit slot =>
    simp only [eval] at h
    split at h
    · rename_i guard
      cases h
      simp [WellFormed, liveCell, nonempty guard.1, guard.2.2.2.1]
    · simp at h
  | complete slot =>
    simp only [eval] at h
    split at h
    · rename_i guard
      cases h
      exact live_wellFormed _ _ _ (nonempty guard.1)
    · simp at h
  | retire slot =>
    simp only [eval] at h
    split at h
    · cases h
      exact quarantined_wellFormed _
    · simp at h

inductive Runs : Cell → List Op → Cell → Prop where
  | nil : Runs c [] c
  | cons : eval c op = some next → Runs next ops result → Runs c (op :: ops) result

theorem runs_preserves (wf : WellFormed c) (run : Runs c ops result) : WellFormed result := by
  induction run with
  | nil => exact wf
  | cons step rest ih => exact ih (eval_preserves wf step)

theorem reachable_wellFormed (run : Runs initialCell ops result) : WellFormed result :=
  runs_preserves initial_wellFormed run

/-- Every successful read has a live object and an extant owner or borrow token. -/
theorem use_valid (h : eval c (.use slot) = some result) :
    c.life = .live ∧ c.phase = .cpu ∧ (has c.owners slot ∨ has c.borrows slot) := by
  simp only [eval] at h
  split at h
  · assumption
  · simp at h

/-- Borrow validity follows globally from preservation, even between reads. -/
theorem borrow_valid (wf : WellFormed c) (loan : has c.borrows slot) : c.life = .live := by
  by_cases live : c.life = .live
  · exact live
  · have empty := wf.2.1 live
    rcases loan with ⟨token, member, _⟩
    simp [empty] at member

theorem no_double_free (wf : WellFormed c) : c.frees ≤ 1 := by
  rw [wf.2.2.2]
  split <;> omega

/-- Freed identities cannot be resurrected or freed again by any instruction. -/
theorem freed_terminal (dead : c.life = .freed) : eval c op = none := by
  cases op <;> simp [eval, dead]

theorem quarantined_terminal (pinned : c.life = .quarantined) : eval c op = none := by
  cases op <;> simp [eval, pinned]

theorem quarantine_keeps_backing (generation : Nat) :
    (quarantinedCell generation).owners = [] ∧
    (quarantinedCell generation).borrows = [] ∧
    (quarantinedCell generation).frees = 0 := by
  simp [quarantinedCell]

theorem freed_run_empty (dead : c.life = .freed) (run : Runs c ops result) :
    ops = [] ∧ result = c := by
  cases run with
  | nil => exact ⟨rfl, rfl⟩
  | cons step rest => simp [freed_terminal dead] at step

theorem fresh_not_freed (wf : WellFormed c) (fresh : c.life = .fresh) : c.frees = 0 := by
  simpa [fresh] using wf.2.2.2

theorem moved_source_absent (tokens : List Token) (source : Nat) :
    ¬ has (withoutSlot tokens source) source := by
  simp [has, withoutSlot]

/-- A move cannot consume a slot belonging to a different allocation identity. -/
theorem wrong_owner_move_rejected (absent : ¬ has c.owners source) :
    eval c (.move source target scope) = none := by
  simp [eval, absent]

theorem borrowed_last_owner_rejected
    (last : withoutSlot c.owners slot = []) (loan : c.borrows ≠ []) :
    eval c (.release slot) = none := by
  simp [eval, cleanup, last, loan]

theorem shared_reuse_rejected (shared : c.owners.length ≠ 1) :
    eval c (.reuse source target scope) = none := by
  simp [eval, shared]

theorem withoutScope_all (tokens : List Token) (scope : Nat)
    (all : ∀ token ∈ tokens, token.scope = scope) : withoutScope tokens scope = [] := by
  induction tokens with
  | nil => rfl
  | cons token rest ih =>
    have head := all token (by simp)
    have tail : ∀ item ∈ rest, item.scope = scope := by
      intro item member
      exact all item (by simp [member])
    simp [withoutScope, head, ih tail]
    exact tail

/-- If all remaining owners belong to the exiting scope and no external borrow
    remains, scope cleanup physically releases the abstract allocation exactly once. -/
theorem scope_no_leak (live : c.life = .live) (cpu : c.phase = .cpu)
    (owners : ∀ token ∈ c.owners, token.scope = scope)
    (borrows : ∀ token ∈ c.borrows, token.scope = scope) :
    eval c (.exit scope) = some (freedCell c.generation) := by
  simp [eval, live, cpu, withoutScope_all _ _ owners,
    withoutScope_all _ _ borrows, cleanup]

theorem pending_no_cpu_access (pending : c.phase = .pending) :
    eval c (.use slot) = none ∧ eval c (.release slot) = none ∧
    eval c (.borrow source target scope) = none ∧
    eval c (.reuse source target scope) = none := by
  simp [eval, pending]

theorem submit_affine (h : eval c (.submit slot) = some result) :
    c.owners.length = 1 ∧ c.borrows = [] ∧ result.phase = .pending := by
  simp only [eval] at h
  split at h
  · rename_i guard
    cases h
    exact ⟨guard.2.2.2.1, guard.2.2.2.2, rfl⟩
  · simp at h

theorem completion_requires_pending (h : eval c (.complete slot) = some result) :
    c.phase = .pending ∧ has c.owners slot ∧ result.phase = .cpu := by
  simp only [eval] at h
  split at h
  · rename_i guard
    cases h
    exact ⟨guard.2.1, guard.2.2, rfl⟩
  · simp at h

inductive Effect where
  | scalar | mmio | signal | managed | float | blocking | lock | native | indirect | cyclic
  deriving DecidableEq, Repr

def IrqSafe : Effect → Prop
  | .scalar | .mmio | .signal => True
  | _ => False

instance (effect : Effect) : Decidable (IrqSafe effect) := by
  cases effect <;> simp [IrqSafe] <;> infer_instance

inductive Command where
  | heap (object : Nat) (op : Op)
  | irqEnter | irqExit
  | effect (effect : Effect)
  deriving DecidableEq, Repr

structure World where
  cells : Nat → Cell := fun _ => initialCell
  inIrq : Bool := false

def initialWorld : World := {}

def step (world : World) : Command → Option World
  | .heap object op =>
    if world.inIrq then none else
    match eval (world.cells object) op with
    | none => none
    | some cell => some { world with cells := fun key =>
        if key = object then cell else world.cells key }
  | .irqEnter =>
    if world.inIrq then none else some { world with inIrq := true }
  | .irqExit =>
    if world.inIrq then some { world with inIrq := false } else none
  | .effect effect =>
    if world.inIrq then (if IrqSafe effect then some world else none) else some world

def WorldWellFormed (world : World) : Prop := ∀ object, WellFormed (world.cells object)

theorem initial_world_wellFormed : WorldWellFormed initialWorld := by
  intro object
  exact initial_wellFormed

theorem step_preserves (wf : WorldWellFormed world)
    (h : step world command = some result) : WorldWellFormed result := by
  cases command with
  | heap object op =>
    simp only [step] at h
    split at h
    · simp at h
    · split at h
      · simp at h
      · rename_i cell computed
        cases h
        intro key
        simp only
        split
        · subst key
          exact eval_preserves (wf object) computed
        · exact wf key
  | irqEnter =>
    simp only [step] at h
    split at h
    · simp at h
    · cases h
      exact wf
  | irqExit =>
    simp only [step] at h
    split at h
    · cases h
      exact wf
    · simp at h
  | effect effect =>
    simp only [step] at h
    split at h
    · split at h
      · cases h
        exact wf
      · simp at h
    · cases h
      exact wf

theorem irq_excludes_heap (irq : world.inIrq = true) :
    step world (.heap object op) = none := by
  simp [step, irq]

theorem irq_effect_safe (irq : world.inIrq = true)
    (h : step world (.effect effect) = some result) : IrqSafe effect := by
  simp only [step, irq, ↓reduceIte] at h
  split at h
  · assumption
  · simp at h

/-- Executable replay uses exactly step, the function proved above. -/
def replay (world : World) (commands : List Command) : Option World :=
  commands.foldlM step world

@[simp] theorem replay_nil : replay world [] = some world := rfl

@[simp] theorem replay_cons : replay world (command :: rest) =
    (step world command).bind (fun next => replay next rest) := rfl

theorem replay_preserves (wf : WorldWellFormed world)
    (h : replay world commands = some result) : WorldWellFormed result := by
  induction commands generalizing world with
  | nil =>
    simp only [replay_nil] at h
    cases h
    exact wf
  | cons command rest ih =>
    simp only [replay_cons] at h
    cases computed : step world command with
    | none => simp [computed] at h
    | some next =>
      simp [computed] at h
      exact ih (step_preserves wf computed) h

theorem checker_sound (h : replay initialWorld commands = some result) :
    WorldWellFormed result := replay_preserves initial_world_wellFormed h

end Minyar
