import Minyar.Contract

namespace Minyar.Examples

open Finite Language

def cpu : Resource := ⟨liveCell [⟨0, 0⟩] [] .cpu 0, .acyclic, 16, none, 0, 1⟩
def request : Dma.Request := submitted cpu 0 7 11 0 1 8
def pending : Resource := { cpu with
  cell := liveCell [⟨0, 0⟩] [] .pending 0
  request := some request
  serial := 1 }
def completion : Dma.Completion := ⟨7, 11, 0, 1, 1, 1, 4⟩
def reclaimed : Resource := { cpu with serial := 1 }

example : resourceEval cpu (.submit 0 7 11 0 1 8) = some pending := by decide
example : resourceEval pending (.reclaim 0 completion) = some reclaimed := by decide
example : resourceEval pending (.reclaim 0 { completion with device := 99 }) = none := by decide
example : resourceEval pending (.reclaim 0 { completion with generation := 2 }) = none := by decide
example : resourceEval pending (.reclaim 0 { completion with length := 17 }) = none := by decide
example : resourceEval pending (.reclaim 1 completion) = none := by decide
example : resourceEval cpu (.reclaim 0 completion) = none := by decide
example : resourceEval pending (.retire 0) =
    some { pending with cell := quarantinedCell 0 } := by decide

def pendingAgain : Resource := { reclaimed with
  cell := liveCell [⟨0, 0⟩] [] .pending 0
  request := some (submitted reclaimed 0 7 11 0 1 8)
  serial := 2 }

example : resourceEval reclaimed (.submit 0 7 11 0 1 8) = some pendingAgain := by decide
example : resourceEval pendingAgain (.reclaim 0 completion) = none := by decide
example : resourceEval pendingAgain (.reclaim 0 { completion with generation := 2, sequence := 2 }) =
    some { reclaimed with serial := 2 } := by decide

def acyclic : Resource := ⟨liveCell [⟨0, 0⟩] [] .cpu 0, .acyclic, 1, none, 0, 1⟩
def traced : Resource := { acyclic with policy := .traced }
def pinned : Resource := { pending with cell := quarantinedCell 0 }

example : closeContext 0 [acyclic, traced, pinned] {} =
    some ([{ acyclic with cell := freedCell 0 }, { traced with cell := freedCell 0 }, pinned],
      ⟨1, 1, 0⟩) := by decide

def retiredFirst : Resource := { pending with cell := quarantinedCell 0 }
def reusedQueueContext : Context := [retiredFirst, cpu]
def freshPending : Resource := { cpu with
  cell := liveCell [⟨0, 0⟩] [] .pending 0
  request := some (submitted { cpu with serial := 1 } 0 7 11 0 1 8)
  serial := 2 }

example : queueAvailable reusedQueueContext (.submit 0 7 11 0 1 8) = false := by decide
example : updateAt (prepare [reclaimed, cpu] (.submit 0 7 11 0 1 8)) 1
    (.submit 0 7 11 0 1 8) = some [reclaimed, freshPending] := by decide
example : resourceEval freshPending (.reclaim 0 completion) = none := by decide
example : resourceEval freshPending (.reclaim 0 { completion with generation := 2, sequence := 2 }) =
    some { cpu with serial := 2 } := by decide

/-- Constructive inhabitants of public resource typing, rather than only
    successful evaluations of the untyped executable helper. -/
def loaned : Resource := { cpu with
  cell := liveCell [⟨0, 0⟩] [⟨1, 0⟩] .cpu 0
  nextSlot := 2 }
def ended : Resource := { cpu with nextSlot := 2 }
def disposed : Resource := { ended with cell := freedCell 0 }
def borrowingProgram : List Action :=
  [.resource 0 (.owner (.borrow 0 1 0)), .resource 0 (.owner (.use 1)),
    .resource 0 (.owner (.endBorrow 1)), .resource 0 (.owner (.release 0))]

theorem borrowing_program_typable : ProgramTyped [cpu] false borrowingProgram [disposed] false := by
  apply ProgramTyped.cons (next := [loaned])
  · exact .resource rfl (.here (.owner rfl (by decide)
      (.borrow (by simp [HasCapability, cpu, liveCell, has]) (by decide))))
  apply ProgramTyped.cons (next := [loaned])
  · exact .resource rfl (.here (.owner rfl (by decide)
      (.useBorrow (by simp [HasCapability, loaned, cpu, liveCell, has]))))
  apply ProgramTyped.cons (next := [ended])
  · exact .resource rfl (.here (.owner rfl (by decide)
      (.endBorrow (by simp [HasCapability, loaned, cpu, liveCell, has]))))
  apply ProgramTyped.cons
  · exact .resource rfl (.here (.owner rfl (by decide)
      (.release (by simp [HasCapability, ended, cpu, liveCell, has]) (by intro _; rfl))))
  · exact .nil

def moved : Resource := { cpu with cell := liveCell [⟨1, 0⟩] [] .cpu 0, nextSlot := 2 }

example : resourceEval cpu (.owner (.move 0 1 0)) = some moved := by decide
example : resourceEval moved (.owner (.retain 1 0 0)) = none := by decide
example : resourceEval ended (.owner (.retain 0 1 0)) = none := by decide
example : DeadSlot moved 0 := by simp [DeadSlot, Active, moved, cpu, liveCell, has]
example : DeadSlot ended 1 := by simp [DeadSlot, Active, ended, cpu, liveCell, has]

theorem cpu_valid : Valid cpu := by
  exact ⟨live_wellFormed _ _ _ (by simp [cpu]),
    by simp [UniqueSlots, TokensUnique, cpu, liveCell],
    by simp [RequestCoherent, cpu, liveCell],
    by simp [SlotsBelow, Active, cpu, liveCell, has]⟩

theorem pending_valid : Valid pending :=
  local_preservation cpu_valid (.submit rfl (by decide) (by decide)
    (.submit (by simp [HasCapability, cpu, liveCell, has]) rfl rfl))

theorem pinned_valid : Valid pinned :=
  local_preservation (action := .retire 0) pending_valid (.retire
    (.retire (by simp [HasCapability, pending, cpu, liveCell, has]) rfl rfl))

example : ¬ Valid { pending with request := none } := by
  intro valid
  have coherent := valid.2.2.1
  simp [RequestCoherent, pending, liveCell] at coherent

example : ¬ Valid { cpu with request := some request } := by
  intro valid
  have coherent := valid.2.2.1
  simp [RequestCoherent, cpu, liveCell] at coherent

def irqFunctions : Functions := fun name => if name = 0 then
  some (.branch (.action (.primitive .mmio)) (.action (.primitive .signal))) else none
def irqTerm : Term := .sequence (.action (.primitive .scalar)) (.call 0)

theorem nested_irq_typable : InterruptTyped irqFunctions irqTerm := by
  refine ⟨[.scalar, .mmio, .signal], ?_, ?_⟩
  · exact .sequence .action (.call rfl (.branch .action .action))
  · intro effect member
    simp only [List.mem_cons, List.not_mem_nil, or_false] at member
    rcases member with rfl | rfl | rfl <;> trivial

theorem nested_irq_executes : Executes irqFunctions irqTerm
    [.primitive .scalar, .primitive .mmio] :=
  .sequence .action (.call rfl (.yes .action))

end Minyar.Examples
