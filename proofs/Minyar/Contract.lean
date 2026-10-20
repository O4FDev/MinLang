import Minyar.Effects

/-! These fully explicit types are the landing contract. They make weakening a
    named theorem to True (or merely counting theorems) fail kernel checking. -/

namespace Minyar.Contract

theorem preservation : ∀ (cell result : Cell) (op : Op),
    WellFormed cell → eval cell op = some result → WellFormed result :=
  fun _ _ _ => eval_preserves

theorem affine_preservation : ∀ (cell result : Cell) (op : Op),
    UniqueSlots cell → eval cell op = some result → UniqueSlots result :=
  fun _ _ _ => eval_preserves_unique

theorem no_use_after_free : ∀ (cell result : Cell) (slot : Nat),
    eval cell (.use slot) = some result →
      cell.life = .live ∧ cell.phase = .cpu ∧ (has cell.owners slot ∨ has cell.borrows slot) :=
  fun _ _ _ => use_valid

theorem no_double_release : ∀ (cell result : Cell) (slot : Nat),
    eval cell (.release slot) = some result → eval result (.release slot) = none :=
  fun _ _ _ => release_once

theorem move_consumes : ∀ (cell result : Cell) (source target scope : Nat),
    UniqueSlots cell → eval cell (.move source target scope) = some result →
      eval result (.use source) = none := fun _ _ _ _ _ => move_invalidates_source

theorem internal_completion_excluded : ∀ (cell result : Cell) (slot : Nat),
    ¬ Typed cell (.complete slot) result := fun _ _ _ => raw_completion_not_typable

theorem dma_bounded : ∀ (cell : Cell) (owner : Nat) (request : Dma.Request)
    (completion : Dma.Completion) (view : Dma.CpuView),
    Dma.reclaim cell owner request completion = some view →
      view.accessible = completion.length ∧ view.accessible ≤ request.submitted ∧
      view.accessible ≤ request.capacity := fun _ _ _ _ _ => Dma.reclaim_prefix_bounded

theorem public_soundness : ∀ (context final : Finite.Context) (state : Language.State)
    (mode finalMode : Bool) (program : List Language.Action),
    Language.Consistent context state → state.inIrq = mode →
      Language.ProgramTyped context mode program final finalMode →
      ∃ result, Language.run state program = some result ∧
        Language.Consistent final result ∧ result.inIrq = finalMode :=
  fun _ _ _ _ _ _ => Language.public_type_soundness

theorem world_scope_cleanup : ∀ (scope : Nat) (context : Finite.Context)
    (ledger : Reclamation.Ledger), Finite.ContextLocal scope context →
    ∃ closed final, Finite.closeContext scope context ledger = some (closed, final) ∧
      Finite.ContextClosed closed ∧
      Reclamation.accounted final = Reclamation.accounted ledger + Finite.liveCount context ∧
      ∀ budget, final.queued ≤ budget →
        Reclamation.outstanding (Reclamation.poll final budget) + Finite.pinnedCount closed =
          final.cycles + Finite.pinnedCount context :=
  fun _ _ ledger ready => Finite.scope_no_leak_modulo_policy ready ledger

theorem compositional_irq_safety : ∀ (functions : Language.Functions) (term : Language.Term)
    (trace : List Language.Action), Language.InterruptTyped functions term →
    Language.Executes functions term trace → ∀ action ∈ trace, IrqSafe action.effect :=
  fun _ _ _ => Language.interrupt_execution_safe

theorem closed_store_cleanup : ∀ (context final : Finite.Context) (state : Language.State)
    (program : List Language.Action) (scope : Nat) (ledger : Reclamation.Ledger),
    Language.Consistent context state → state.inIrq = false →
    Language.ProgramTyped context false program final false →
    Finite.ContextLocal scope final →
    ∃ result exited closed debt,
      Language.run state program = some result ∧ Language.Consistent final result ∧
      Finite.closeContext scope final ledger = some (closed, debt) ∧ Finite.ContextClosed closed ∧
      Language.Consistent closed exited ∧
      (∀ index, (exited.heap index).allocated = true →
        ∃ resource, closed[index]? = some resource ∧ resource.cell.life = .quarantined) ∧
      ∀ budget, debt.queued ≤ budget →
        Reclamation.outstanding (Reclamation.poll debt budget) + Finite.pinnedCount closed =
          debt.cycles + Finite.pinnedCount final :=
  fun _ _ _ _ _ ledger consistent irq typing ready =>
    Language.program_scope_cleanup consistent irq typing ready ledger

theorem global_nonce_monotone : ∀ (context final : Finite.Context) (mode finalMode : Bool)
    (program : List Language.Action),
    Language.ProgramTyped context mode program final finalMode →
      Language.contextNonce context ≤ Language.contextNonce final :=
  fun _ _ _ _ _ => Language.program_nonce_monotone

theorem queue_reuse_rejects_old_completion : ∀ (context : Finite.Context)
    (resource pending : Finite.Resource) (owner device queue descriptor queueEpoch length : Nat)
    (completion : Dma.Completion),
    Language.resourceEval { resource with serial := Language.contextNonce context }
      (.submit owner device queue descriptor queueEpoch length) = some pending →
    completion.generation ≤ Language.contextNonce context →
      Language.resourceEval pending (.reclaim owner completion) = none :=
  fun _ _ _ _ _ _ _ _ _ _ => Language.fresh_submit_rejects_old_completion

theorem active_or_quarantined_queue_rejects_submit : ∀ (state : Language.State)
    (resource : Finite.Resource) (request : Dma.Request)
    (index owner device queue descriptor queueEpoch length : Nat),
    resource ∈ state.context → resource.request = some request → request.queue = queue →
      Language.step state (.resource index (.submit owner device queue descriptor queueEpoch length)) = none :=
  fun _ _ _ _ _ _ _ _ _ _ => Language.public_busy_queue_rejected

theorem every_public_submit_advances_nonce : ∀ (context next : Finite.Context)
    (index owner device queue descriptor queueEpoch length : Nat),
    Language.ActionTyped context false
      (.resource index (.submit owner device queue descriptor queueEpoch length)) next false →
      Language.contextNonce context < Language.contextNonce next :=
  fun _ _ _ _ _ _ _ _ _ => Language.public_submit_nonce_strict

theorem historical_replay_rejection (before after current : Finite.Context)
    (resource pending : Finite.Resource)
    (oldIndex oldOwner oldDevice oldQueue oldDescriptor oldEpoch oldLength
      owner device queue descriptor queueEpoch length : Nat)
    (program : List Language.Action) (completion : Dma.Completion) :
    Language.ActionTyped before false
      (.resource oldIndex (.submit oldOwner oldDevice oldQueue oldDescriptor oldEpoch oldLength))
      after false →
    Language.ProgramTyped after false program current false →
    Language.resourceEval { resource with serial := Language.contextNonce current }
      (.submit owner device queue descriptor queueEpoch length) = some pending →
    completion.generation = Language.contextNonce before + 1 →
    Language.resourceEval pending (.reclaim owner completion) = none := by
  intro first history fresh old
  exact Language.historical_replay_rejected first history fresh old

theorem public_dma_coherence (context final : Finite.Context) (state : Language.State)
    (mode finalMode : Bool) (program : List Language.Action) :
    Language.Consistent context state → state.inIrq = mode →
    Language.ProgramTyped context mode program final finalMode →
    ∃ result, Language.run state program = some result ∧ Finite.ContextValid final ∧
      Finite.QueuesUnique final ∧ ∀ resource ∈ final, Finite.RequestCoherent resource := by
  intro consistent irq typing
  exact Language.public_context_coherence consistent irq typing

theorem canonical_reclaim (resource next : Finite.Resource) (owner : Nat)
    (completion : Dma.Completion) : Finite.Valid resource →
    Language.resourceEval resource (.reclaim owner completion) = some next →
    ∃ request, resource.request = some request ∧ Finite.RequestBound resource request ∧
      owner = request.ownerSlot ∧ resource.cell.generation = request.cellGeneration ∧
      Dma.Matches request completion ∧ next.request = none := by
  intro valid executed
  exact Language.canonical_reclaim_origin valid executed

theorem stale_capability (context final : Finite.Context) (index slot : Nat)
    (mode finalMode : Bool) (program : List Language.Action) :
    Language.DeadAt context index slot →
    Language.ProgramTyped context mode program final finalMode →
    ∃ resource, final[index]? = some resource ∧ Finite.DeadSlot resource slot ∧
      Language.resourceEval resource (.owner (.use slot)) = none ∧
      Language.resourceEval resource (.owner (.release slot)) = none := by
  intro dead typing
  exact Language.stale_capability_never_returns dead typing

theorem consumed_move_dead (resource next : Finite.Resource) (source target scope : Nat) :
    Finite.Valid resource → Language.LocalTyped resource (.owner (.move source target scope)) next →
    Finite.DeadSlot next source := by
  intro valid typing
  exact Language.move_marks_dead valid typing

theorem ended_borrow_dead (resource next : Finite.Resource) (slot : Nat) :
    Finite.Valid resource → Language.LocalTyped resource (.owner (.endBorrow slot)) next →
    Finite.DeadSlot next slot := by
  intro valid typing
  exact Language.end_borrow_marks_dead valid typing

theorem scope_preserves_queue_identity (context closed : Finite.Context) (scope : Nat)
    (ledger debt : Reclamation.Ledger) : Finite.QueuesUnique context →
    Finite.closeContext scope context ledger = some (closed, debt) → Finite.QueuesUnique closed := by
  intro unique execution
  exact Finite.close_context_queues_unique unique execution

end Minyar.Contract
