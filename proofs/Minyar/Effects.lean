import Minyar.Language

namespace Minyar.Language

inductive Term where
  | action (action : Action)
  | sequence (first second : Term)
  | branch (yes no : Term)
  | call (function : Nat)

abbrev Functions := Nat → Option Term

/-- Effects are derived from actual action syntax, both branches, and callee
    bodies. There is no rule accepting a caller-supplied summary for a call. -/
inductive HasEffects (functions : Functions) : Term → List Effect → Prop where
  | action : HasEffects functions (.action action) [action.effect]
  | sequence : HasEffects functions first left → HasEffects functions second right →
      HasEffects functions (.sequence first second) (left ++ right)
  | branch : HasEffects functions yes left → HasEffects functions no right →
      HasEffects functions (.branch yes no) (left ++ right)
  | call : functions name = some body → HasEffects functions body effects →
      HasEffects functions (.call name) effects

inductive Executes (functions : Functions) : Term → List Action → Prop where
  | action : Executes functions (.action action) [action]
  | sequence : Executes functions first left → Executes functions second right →
      Executes functions (.sequence first second) (left ++ right)
  | yes : Executes functions yes trace → Executes functions (.branch yes no) trace
  | no : Executes functions no trace → Executes functions (.branch yes no) trace
  | call : functions name = some body → Executes functions body trace →
      Executes functions (.call name) trace

theorem effects_cover_execution (typing : HasEffects functions term effects)
    (execution : Executes functions term trace) :
    ∀ action ∈ trace, action.effect ∈ effects := by
  induction typing generalizing trace with
  | action =>
    cases execution
    intro action member
    simp only [List.mem_singleton] at member
    subst action
    simp
  | sequence left right ihLeft ihRight =>
    cases execution with
    | sequence runLeft runRight =>
      intro action member
      rcases List.mem_append.mp member with inLeft | inRight
      · exact List.mem_append_left _ (ihLeft runLeft action inLeft)
      · exact List.mem_append_right _ (ihRight runRight action inRight)
  | branch left right ihLeft ihRight =>
    cases execution with
    | yes run =>
      intro action member
      exact List.mem_append_left _ (ihLeft run action member)
    | no run =>
      intro action member
      exact List.mem_append_right _ (ihRight run action member)
  | call found body ih =>
    cases execution with
    | call actual run =>
      have same := found.symm.trans actual
      cases same
      exact ih run

def InterruptTyped (functions : Functions) (term : Term) : Prop :=
  ∃ effects, HasEffects functions term effects ∧ ∀ effect ∈ effects, IrqSafe effect

theorem interrupt_execution_safe (typing : InterruptTyped functions term)
    (execution : Executes functions term trace) :
    ∀ action ∈ trace, IrqSafe action.effect := by
  rcases typing with ⟨effects, derived, safe⟩
  intro action member
  exact safe action.effect (effects_cover_execution derived execution action member)

theorem interrupt_no_ownership (typing : InterruptTyped functions term)
    (execution : Executes functions term trace) :
    ∀ index operation, Action.resource index operation ∉ trace := by
  intro index operation member
  have bad := interrupt_execution_safe typing execution _ member
  simp [Action.effect, IrqSafe] at bad

theorem interrupt_no_allocation (typing : InterruptTyped functions term)
    (execution : Executes functions term trace) :
    ∀ owner scope capacity policy, Action.allocate owner scope capacity policy ∉ trace := by
  intro owner scope capacity policy member
  have bad := interrupt_execution_safe typing execution _ member
  simp [Action.effect, IrqSafe] at bad

theorem interrupt_no_blocking (typing : InterruptTyped functions term)
    (execution : Executes functions term trace) :
    Action.primitive .blocking ∉ trace := by
  intro member
  have bad := interrupt_execution_safe typing execution _ member
  simp [Action.effect, Primitive.effect, IrqSafe] at bad

/-- Composition: function/branch effect derivations cover the exact action trace
    whose resource typing supplies public progress and store preservation. -/
theorem function_type_soundness
    (effects : HasEffects functions term summary) (execution : Executes functions term trace)
    (consistent : Consistent context state) (irq : state.inIrq = mode)
    (resources : ProgramTyped context mode trace final finalMode) :
    (∀ action ∈ trace, action.effect ∈ summary) ∧
      ∃ result, run state trace = some result ∧ Consistent final result ∧ result.inIrq = finalMode :=
  ⟨effects_cover_execution effects execution, public_type_soundness consistent irq resources⟩

end Minyar.Language
