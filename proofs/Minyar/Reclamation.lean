import Minyar.Ownership

/-! Physical reclamation is distinct from logical ownership. A finite rootless
    component contributes explicit work, either queued immediately (acyclic) or
    held by the traced-cycle policy. Polling never invents collector progress. -/

namespace Minyar.Reclamation

inductive Policy where
  | acyclic | traced
  deriving DecidableEq, Repr

structure Ledger where
  queued : Nat := 0
  cycles : Nat := 0
  reclaimed : Nat := 0
  deriving DecidableEq, Repr

def outstanding (ledger : Ledger) : Nat := ledger.queued + ledger.cycles

def accounted (ledger : Ledger) : Nat := outstanding ledger + ledger.reclaimed

/-- A work unit abstracts one finite destructor/edge obligation. No bound on
    the number of units in an arbitrary source heap is asserted. -/
def retire (ledger : Ledger) (policy : Policy) (work : Nat) : Ledger :=
  match policy with
  | .acyclic => { ledger with queued := ledger.queued + work }
  | .traced => { ledger with cycles := ledger.cycles + work }

def poll (ledger : Ledger) (budget : Nat) : Ledger :=
  let serviced := min budget ledger.queued
  { ledger with
    queued := ledger.queued - serviced
    reclaimed := ledger.reclaimed + serviced }

/-- collect is the abstract event that a separate cycle collector has proved
    these rootless traced components collectible. It is not triggered by poll. -/
def collect (ledger : Ledger) : Ledger :=
  { ledger with queued := ledger.queued + ledger.cycles, cycles := 0 }

theorem retire_accounts (ledger : Ledger) (policy : Policy) (work : Nat) :
    accounted (retire ledger policy work) = accounted ledger + work := by
  cases policy <;> simp [accounted, outstanding, retire] <;> omega

theorem poll_work_bound (ledger : Ledger) (budget : Nat) :
    (poll ledger budget).reclaimed - ledger.reclaimed ≤ budget := by
  have bounded := Nat.min_le_left budget ledger.queued
  simp only [poll]
  omega

theorem poll_preserves_accounting (ledger : Ledger) (budget : Nat) :
    accounted (poll ledger budget) = accounted ledger := by
  have bounded := Nat.min_le_right budget ledger.queued
  simp [accounted, outstanding, poll]
  omega

theorem poll_preserves_cycles (ledger : Ledger) (budget : Nat) :
    (poll ledger budget).cycles = ledger.cycles := rfl

theorem collect_preserves_accounting (ledger : Ledger) :
    accounted (collect ledger) = accounted ledger := by
  simp [accounted, outstanding, collect]

/-- No leak modulo cycles: sufficient polling discharges all queued acyclic
    work, leaving exactly the explicitly recorded traced-cycle obligations. -/
theorem drain_modulo_cycles (ledger : Ledger) (enough : ledger.queued ≤ budget) :
    outstanding (poll ledger budget) = ledger.cycles := by
  simp [outstanding, poll, Nat.min_eq_right enough]

/-- Conditional liveness: after a legitimate cycle collection event, a finite
    sufficient service budget discharges every outstanding obligation. -/
theorem collect_then_drain (ledger : Ledger)
    (enough : ledger.queued + ledger.cycles ≤ budget) :
    outstanding (poll (collect ledger) budget) = 0 := by
  simpa [collect] using drain_modulo_cycles (collect ledger) enough

def polls (ledger : Ledger) (budgets : List Nat) : Ledger := budgets.foldl poll ledger

@[simp] theorem polls_nil : polls ledger [] = ledger := rfl

@[simp] theorem polls_cons : polls ledger (budget :: rest) =
    polls (poll ledger budget) rest := rfl

theorem polls_accounting (ledger : Ledger) (budgets : List Nat) :
    accounted (polls ledger budgets) = accounted ledger := by
  induction budgets generalizing ledger with
  | nil => rfl
  | cons budget rest ih =>
    rw [polls_cons, ih, poll_preserves_accounting]

theorem polls_queued (ledger : Ledger) (budgets : List Nat) :
    (polls ledger budgets).queued = ledger.queued - budgets.sum := by
  induction budgets generalizing ledger with
  | nil => simp [polls]
  | cons budget rest ih =>
    simp only [polls_cons, ih, poll, List.sum_cons]
    omega

theorem finite_service_drains (ledger : Ledger) (budgets : List Nat)
    (enough : ledger.queued ≤ budgets.sum) : (polls ledger budgets).queued = 0 := by
  rw [polls_queued]
  omega

/-- The frame/scope boundary logically frees a fully local component and records
    its physical cleanup debt. The work bound and policy must be supplied by the
    runtime graph interpretation; this function does not discover heap cycles. -/
def exitScope (cell : Cell) (scope : Nat) (ledger : Ledger)
    (policy : Policy) (work : Nat) : Option (Cell × Ledger) := do
  let next ← eval cell (.exit scope)
  if next.life = .freed then pure (next, retire ledger policy work)
  else pure (next, ledger)

theorem scope_exit_records_debt (live : cell.life = .live) (cpu : cell.phase = .cpu)
    (owners : ∀ token ∈ cell.owners, token.scope = scope)
    (borrows : ∀ token ∈ cell.borrows, token.scope = scope) :
    exitScope cell scope ledger policy work =
      some (freedCell cell.generation, retire ledger policy work) := by
  simp [exitScope, scope_no_leak live cpu owners borrows, freedCell]

end Minyar.Reclamation
