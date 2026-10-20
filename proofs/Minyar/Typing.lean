import Minyar.Ownership

/-! Resource typing is an independent inductive judgment. Its constructors contain
    slot/phase premises, not an invocation of eval or WellFormed. Progress relates
    these typing rules to the executable operational semantics. -/

namespace Minyar

inductive Capability where
  | owner (phase : Phase)
  | borrowed
  deriving DecidableEq, Repr

def HasCapability (cell : Cell) (slot : Nat) : Capability → Prop
  | .owner phase => cell.life = .live ∧ cell.phase = phase ∧ has cell.owners slot
  | .borrowed => cell.life = .live ∧ cell.phase = .cpu ∧ has cell.borrows slot

inductive Value where
  | scalar (value : Nat)
  | reference (object slot : Nat) (capability : Capability)
  deriving DecidableEq, Repr

def ValueTyped (world : World) : Value → Prop
  | .scalar _ => True
  | .reference object slot capability => HasCapability (world.cells object) slot capability

def cleanupResult (owners borrows : List Token) (generation : Nat) : Cell :=
  if owners = [] then freedCell generation else liveCell owners borrows .cpu generation

theorem cleanup_progress (safe : owners = [] → borrows = []) :
    cleanup owners borrows generation = some (cleanupResult owners borrows generation) := by
  by_cases empty : owners = []
  · simp [cleanup, cleanupResult, empty, safe empty]
  · simp [cleanup, cleanupResult, empty]

inductive Typed : Cell → Op → Cell → Prop where
  | alloc (fresh : cell.life = .fresh) :
      Typed cell (.alloc slot scope) (liveCell [⟨slot, scope⟩] [] .cpu 0)
  | retain (source : HasCapability cell src (.owner .cpu)) (target : unused cell dst) :
      Typed cell (.retain src dst scope)
        (liveCell (⟨dst, scope⟩ :: cell.owners) cell.borrows .cpu cell.generation)
  | move (source : HasCapability cell src (.owner .cpu)) (target : unused cell dst) :
      Typed cell (.move src dst scope)
        (liveCell (⟨dst, scope⟩ :: withoutSlot cell.owners src)
          cell.borrows .cpu cell.generation)
  | borrow (source : HasCapability cell src (.owner .cpu)) (target : unused cell dst) :
      Typed cell (.borrow src dst scope)
        (liveCell cell.owners (⟨dst, scope⟩ :: cell.borrows) .cpu cell.generation)
  | endBorrow (source : HasCapability cell slot .borrowed) :
      Typed cell (.endBorrow slot)
        (liveCell cell.owners (withoutSlot cell.borrows slot) .cpu cell.generation)
  | useOwner (source : HasCapability cell slot (.owner .cpu)) :
      Typed cell (.use slot) cell
  | useBorrow (source : HasCapability cell slot .borrowed) :
      Typed cell (.use slot) cell
  | release (source : HasCapability cell slot (.owner .cpu))
      (safe : withoutSlot cell.owners slot = [] → cell.borrows = []) :
      Typed cell (.release slot)
        (cleanupResult (withoutSlot cell.owners slot) cell.borrows cell.generation)
  | reuse (source : HasCapability cell src (.owner .cpu)) (target : unused cell dst)
      (unique : cell.owners.length = 1) (noLoans : cell.borrows = []) :
      Typed cell (.reuse src dst scope) (liveCell [⟨dst, scope⟩] [] .cpu (cell.generation + 1))
  | exit (live : cell.life = .live) (cpu : cell.phase = .cpu)
      (safe : withoutScope cell.owners scope = [] → withoutScope cell.borrows scope = []) :
      Typed cell (.exit scope) (cleanupResult (withoutScope cell.owners scope)
        (withoutScope cell.borrows scope) cell.generation)
  | submit (source : HasCapability cell slot (.owner .cpu))
      (unique : cell.owners.length = 1) (noLoans : cell.borrows = []) :
      Typed cell (.submit slot) (liveCell cell.owners [] .pending cell.generation)
  | retire (source : HasCapability cell slot (.owner .pending))
      (unique : cell.owners.length = 1) (noLoans : cell.borrows = []) :
      Typed cell (.retire slot) (quarantinedCell cell.generation)

/-- Progress: every resource-typed command executes to its specified next state. -/
theorem typed_progress (typing : Typed cell op result) : eval cell op = some result := by
  cases typing <;> simp_all [eval, HasCapability, cleanup_progress]

/-- Preservation: execution of a typed command preserves heap/borrow safety. -/
theorem typed_preservation (wf : WellFormed cell) (typing : Typed cell op result) :
    WellFormed result := eval_preserves wf (typed_progress typing)

/-- Completion is an internal transition; no bare completion command is typable. -/
theorem raw_completion_not_typable : ¬ Typed cell (.complete owner) result := by
  intro typing
  cases typing

inductive TypedProgram : Cell → List Op → Cell → Prop where
  | nil : TypedProgram cell [] cell
  | cons : Typed cell op next → TypedProgram next ops result →
      TypedProgram cell (op :: ops) result

theorem typed_program_runs (typing : TypedProgram cell ops result) : Runs cell ops result := by
  induction typing with
  | nil => exact .nil
  | cons head tail ih => exact .cons (typed_progress head) ih

theorem type_soundness (wf : WellFormed cell) (typing : TypedProgram cell ops result) :
    Runs cell ops result ∧ WellFormed result :=
  ⟨typed_program_runs typing, runs_preserves wf (typed_program_runs typing)⟩

theorem typed_borrow_live (typing : ValueTyped world (.reference object slot .borrowed)) :
    (world.cells object).life = .live := typing.1

end Minyar
