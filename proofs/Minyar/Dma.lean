import Minyar.Ownership

/-! A refinement of the trusted completion command for the deterministic DMA
    backend. This checks a frozen completion snapshot; it does not prove the
    fences that produce that snapshot or the virtio one-shot hardware protocol. -/

namespace Minyar.Dma

structure Request where
  ownerSlot : Nat
  cellGeneration : Nat
  device : Nat
  queue : Nat
  slot : Nat
  generation : Nat
  queueEpoch : Nat
  submitted : Nat
  capacity : Nat
  deriving DecidableEq, Repr

/- A Request is the frozen CURRENT outstanding request established at submission,
   including queue.active's allocation association and the queue's current request
   generation. Establishing that association from the concrete registry is an
   explicit construction premise; two arbitrary matching wire snapshots alone
   cannot establish it. ownerSlot and cellGeneration bind its local capability. -/

structure Completion where
  device : Nat
  queue : Nat
  slot : Nat
  generation : Nat
  queueEpoch : Nat
  sequence : Nat
  length : Nat
  deriving DecidableEq, Repr

def Matches (request : Request) (completion : Completion) : Prop :=
  completion.device = request.device ∧
  completion.queue = request.queue ∧
  completion.slot = request.slot ∧
  completion.generation = request.generation ∧
  completion.queueEpoch = request.queueEpoch ∧
  completion.sequence = request.generation ∧
  completion.sequence ≠ 0 ∧
  completion.length ≤ request.submitted ∧
  completion.length ≤ request.capacity

instance (request : Request) (completion : Completion) :
    Decidable (Matches request completion) :=
  inferInstanceAs (Decidable (
    completion.device = request.device ∧
    completion.queue = request.queue ∧
    completion.slot = request.slot ∧
    completion.generation = request.generation ∧
    completion.queueEpoch = request.queueEpoch ∧
    completion.sequence = request.generation ∧
    completion.sequence ≠ 0 ∧
    completion.length ≤ request.submitted ∧
    completion.length ≤ request.capacity))

/-- A CpuView contains exactly the acquired prefix, never submitted capacity.
    The cell transition still checks the pending phase and the owner token. -/
structure CpuView where
  cell : Cell
  accessible : Nat
  deriving DecidableEq, Repr

def reclaim (cell : Cell) (owner : Nat) (request : Request)
    (completion : Completion) : Option CpuView :=
  if owner = request.ownerSlot ∧ cell.generation = request.cellGeneration ∧
      Matches request completion then
    (eval cell (.complete owner)).map fun next => ⟨next, completion.length⟩
  else none

theorem reclaim_guard (h : reclaim cell owner request completion = some result) :
    owner = request.ownerSlot ∧ cell.generation = request.cellGeneration ∧
    Matches request completion := by
  unfold reclaim at h
  split at h
  · assumption
  · simp at h

theorem reclaim_matches (h : reclaim cell owner request completion = some result) :
    Matches request completion := (reclaim_guard h).2.2

theorem reclaim_prefix_bounded
    (h : reclaim cell owner request completion = some result) :
    result.accessible = completion.length ∧
    result.accessible ≤ request.submitted ∧ result.accessible ≤ request.capacity := by
  have guard := reclaim_guard h
  rw [reclaim, if_pos guard] at h
  cases computed : eval cell (.complete owner) with
  | none => simp [computed] at h
  | some next =>
    simp [computed] at h
    cases h
    have matching := guard.2.2
    exact ⟨rfl, matching.2.2.2.2.2.2.2.1, matching.2.2.2.2.2.2.2.2⟩

theorem reclaim_preserves (wf : WellFormed cell)
    (h : reclaim cell owner request completion = some result) :
    WellFormed result.cell ∧ cell.phase = .pending ∧ result.cell.phase = .cpu := by
  have guard := reclaim_guard h
  rw [reclaim, if_pos guard] at h
  cases computed : eval cell (.complete owner) with
  | none => simp [computed] at h
  | some next =>
    simp [computed] at h
    cases h
    have protocol := completion_requires_pending computed
    exact ⟨eval_preserves wf computed, protocol.1, protocol.2.2⟩

theorem mismatched_device_rejected (wrong : completion.device ≠ request.device) :
    reclaim cell owner request completion = none := by
  simp [reclaim, Matches, wrong]

theorem mismatched_queue_rejected (wrong : completion.queue ≠ request.queue) :
    reclaim cell owner request completion = none := by
  simp [reclaim, Matches, wrong]

theorem mismatched_slot_rejected (wrong : completion.slot ≠ request.slot) :
    reclaim cell owner request completion = none := by
  simp [reclaim, Matches, wrong]

theorem stale_generation_rejected (wrong : completion.generation ≠ request.generation) :
    reclaim cell owner request completion = none := by
  simp [reclaim, Matches, wrong]

theorem stale_queue_epoch_rejected (wrong : completion.queueEpoch ≠ request.queueEpoch) :
    reclaim cell owner request completion = none := by
  simp [reclaim, Matches, wrong]

theorem unpublished_rejected (unpublished : completion.sequence = 0) :
    reclaim cell owner request completion = none := by
  simp [reclaim, Matches, unpublished]

theorem stale_sequence_rejected (wrong : completion.sequence ≠ request.generation) :
    reclaim cell owner request completion = none := by
  simp [reclaim, Matches, wrong]

theorem oversized_completion_rejected (oversized : request.submitted < completion.length) :
    reclaim cell owner request completion = none := by
  have bound : ¬ completion.length ≤ request.submitted := by omega
  simp [reclaim, Matches, bound]

theorem capacity_exceeded_rejected (oversized : request.capacity < completion.length) :
    reclaim cell owner request completion = none := by
  have bound : ¬ completion.length ≤ request.capacity := by omega
  simp [reclaim, Matches, bound]

theorem wrong_owner_rejected (wrong : owner ≠ request.ownerSlot) :
    reclaim cell owner request completion = none := by
  simp [reclaim, wrong]

theorem stale_cell_generation_rejected (wrong : cell.generation ≠ request.cellGeneration) :
    reclaim cell owner request completion = none := by
  simp [reclaim, wrong]

theorem reclaim_binds_capability
    (h : reclaim cell owner request completion = some result) :
    owner = request.ownerSlot ∧ cell.generation = request.cellGeneration := by
  exact ⟨(reclaim_guard h).1, (reclaim_guard h).2.1⟩

end Minyar.Dma
