import Minyar.Typing

/-! Slot uniqueness is a separate reachable invariant, stronger than physical
    liveness alone. It excludes duplicate owners, duplicate loans, and owner/loan
    collisions even when their scope labels differ. -/

namespace Minyar

def TokensUnique (owners borrows : List Token) : Prop :=
  ((owners ++ borrows).map Token.slot).Nodup

def UniqueSlots (cell : Cell) : Prop := TokensUnique cell.owners cell.borrows

theorem initial_unique : UniqueSlots initialCell := by
  simp [UniqueSlots, TokensUnique, initialCell]

theorem unique_sublist (unique : TokensUnique owners borrows)
    (ownerSub : List.Sublist nextOwners owners) (borrowSub : List.Sublist nextBorrows borrows) :
    TokensUnique nextOwners nextBorrows :=
  ((ownerSub.append borrowSub).map Token.slot).nodup unique

theorem unique_filter (unique : TokensUnique owners borrows) (ownerTest borrowTest : Token → Bool) :
    TokensUnique (owners.filter ownerTest) (borrows.filter borrowTest) :=
  unique_sublist unique List.filter_sublist List.filter_sublist

theorem fresh_owner_unique (unique : TokensUnique owners borrows)
    (fresh : ¬ has owners target ∧ ¬ has borrows target) :
    TokensUnique (⟨target, scope⟩ :: owners) borrows := by
  change (target :: (owners ++ borrows).map Token.slot).Nodup
  apply List.nodup_cons.mpr
  constructor
  · simpa [has, List.mem_map] using fresh
  · exact unique

theorem fresh_borrow_unique (unique : TokensUnique owners borrows)
    (fresh : ¬ has owners target ∧ ¬ has borrows target) :
    TokensUnique owners (⟨target, scope⟩ :: borrows) := by
  simp only [TokensUnique, List.map_append, List.map_cons]
  apply (List.pairwise_middle (R := fun a b : Nat => a ≠ b) (fun h => Ne.symm h)).mpr
  apply List.nodup_cons.mpr
  constructor
  · simpa [has, List.mem_map] using fresh
  · simpa [TokensUnique, List.map_append] using unique

theorem has_sublist (sub : List.Sublist smaller larger) (present : has smaller slot) : has larger slot := by
  rcases present with ⟨token, member, eq⟩
  exact ⟨token, sub.subset member, eq⟩

theorem cleanup_unique (unique : TokensUnique owners borrows)
    (h : cleanup owners borrows generation = some result) : UniqueSlots result := by
  unfold cleanup at h
  split at h
  · split at h
    · cases h
      simp [UniqueSlots, TokensUnique, freedCell]
    · simp at h
  · cases h
    exact unique

theorem eval_preserves_unique (unique : UniqueSlots cell)
    (h : eval cell op = some result) : UniqueSlots result := by
  cases op with
  | alloc slot scope =>
    simp only [eval] at h
    split at h
    · cases h
      simp [UniqueSlots, TokensUnique, liveCell]
    · simp at h
  | retain source target scope =>
    simp only [eval] at h
    split at h
    · rename_i guard
      cases h
      exact fresh_owner_unique unique guard.2.2.2
    · simp at h
  | move source target scope =>
    simp only [eval] at h
    split at h
    · rename_i guard
      cases h
      apply fresh_owner_unique
      · exact unique_sublist unique List.filter_sublist (List.Sublist.refl _)
      · exact ⟨fun bad => guard.2.2.2.1 (has_sublist List.filter_sublist bad), guard.2.2.2.2⟩
    · simp at h
  | borrow source target scope =>
    simp only [eval] at h
    split at h
    · rename_i guard
      cases h
      exact fresh_borrow_unique unique guard.2.2.2
    · simp at h
  | endBorrow slot =>
    simp only [eval] at h
    split at h
    · cases h
      exact unique_sublist unique (List.Sublist.refl _) List.filter_sublist
    · simp at h
  | use slot =>
    simp only [eval] at h
    split at h
    · cases h
      exact unique
    · simp at h
  | release slot =>
    simp only [eval] at h
    split at h
    · exact cleanup_unique
        (unique_sublist unique List.filter_sublist (List.Sublist.refl _)) h
    · simp at h
  | reuse source target scope =>
    simp only [eval] at h
    split at h
    · cases h
      simp [UniqueSlots, TokensUnique, liveCell]
    · simp at h
  | exit scope =>
    simp only [eval] at h
    split at h
    · exact cleanup_unique (unique_filter unique _ _) h
    · simp at h
  | submit slot =>
    simp only [eval] at h
    split at h
    · cases h
      exact unique_sublist unique (List.Sublist.refl _) (List.nil_sublist _)
    · simp at h
  | complete slot =>
    simp only [eval] at h
    split at h
    · cases h
      exact unique
    · simp at h
  | retire slot =>
    simp only [eval] at h
    split at h
    · cases h
      simp [UniqueSlots, TokensUnique, quarantinedCell]
    · simp at h

theorem runs_unique (unique : UniqueSlots cell) (run : Runs cell ops result) :
    UniqueSlots result := by
  induction run with
  | nil => exact unique
  | cons step rest ih => exact ih (eval_preserves_unique unique step)

theorem reachable_unique (run : Runs initialCell ops result) : UniqueSlots result :=
  runs_unique initial_unique run

theorem affine_type_soundness (wf : WellFormed cell) (unique : UniqueSlots cell)
    (typing : TypedProgram cell ops result) :
    Runs cell ops result ∧ WellFormed result ∧ UniqueSlots result :=
  ⟨typed_program_runs typing, (type_soundness wf typing).2,
    runs_unique unique (typed_program_runs typing)⟩

def WorldUnique (world : World) : Prop := ∀ object, UniqueSlots (world.cells object)

theorem step_unique (unique : WorldUnique world)
    (h : step world command = some result) : WorldUnique result := by
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
          exact eval_preserves_unique (unique object) computed
        · exact unique key
  | irqEnter =>
    simp only [step] at h
    split at h
    · simp at h
    · cases h
      exact unique
  | irqExit =>
    simp only [step] at h
    split at h
    · cases h
      exact unique
    · simp at h
  | effect effect =>
    simp only [step] at h
    split at h
    · split at h
      · cases h
        exact unique
      · simp at h
    · cases h
      exact unique

theorem replay_unique (unique : WorldUnique world)
    (h : replay world commands = some result) : WorldUnique result := by
  induction commands generalizing world with
  | nil =>
    simp only [replay_nil] at h
    cases h
    exact unique
  | cons command rest ih =>
    simp only [replay_cons] at h
    cases computed : step world command with
    | none => simp [computed] at h
    | some next =>
      simp [computed] at h
      exact ih (step_unique unique computed) h

theorem checker_affine_sound (h : replay initialWorld commands = some result) :
    WorldWellFormed result ∧ WorldUnique result :=
  ⟨checker_sound h, replay_unique (fun _ => initial_unique) h⟩

theorem has_iff_slot_mem (tokens : List Token) (slot : Nat) :
    has tokens slot ↔ slot ∈ tokens.map Token.slot := by
  simp [has, List.mem_map]

theorem owner_not_borrowed (unique : UniqueSlots cell) (owned : has cell.owners slot) :
    ¬ has cell.borrows slot := by
  have together : (cell.owners.map Token.slot ++ cell.borrows.map Token.slot).Nodup := by
    simpa [UniqueSlots, TokensUnique, List.map_append] using unique
  have disjoint := (List.pairwise_append.mp together).2.2
  intro borrowed
  exact disjoint slot ((has_iff_slot_mem _ _).mp owned) slot
    ((has_iff_slot_mem _ _).mp borrowed) rfl

theorem move_invalidates_source (unique : UniqueSlots cell)
    (h : eval cell (.move source target scope) = some result) :
    eval result (.use source) = none := by
  simp only [eval] at h
  split at h
  · rename_i guard
    have noLoan := owner_not_borrowed unique guard.2.2.1
    have different : target ≠ source := by
      intro same
      exact guard.2.2.2.1 (by simpa [same] using guard.2.2.1)
    cases h
    have noOwner : ¬ has (⟨target, scope⟩ :: withoutSlot cell.owners source) source := by
      rintro ⟨token, member, eq⟩
      rcases List.mem_cons.mp member with head | tail
      · subst token
        exact different eq
      · exact moved_source_absent _ _ ⟨token, tail, eq⟩
    simp [eval, liveCell, noOwner, noLoan]
  · simp at h

theorem borrow_postcondition (h : eval cell (.borrow source target scope) = some result) :
    result.owners = cell.owners ∧ has result.borrows target ∧
      result.life = .live ∧ result.phase = .cpu := by
  simp only [eval] at h
  split at h
  · cases h
    exact ⟨rfl, ⟨⟨target, scope⟩, by simp [liveCell], rfl⟩, rfl, rfl⟩
  · simp at h

theorem release_once (first : eval cell (.release slot) = some result) :
    eval result (.release slot) = none := by
  simp only [eval] at first
  split at first
  · unfold cleanup at first
    split at first
    · split at first
      · cases first
        simp [eval, freedCell]
      · simp at first
    · cases first
      simp [eval, liveCell, moved_source_absent]
  · simp at first

theorem reuse_postcondition (h : eval cell (.reuse source target scope) = some result) :
    cell.owners.length = 1 ∧ cell.borrows = [] ∧
      result.owners = [⟨target, scope⟩] ∧ result.generation = cell.generation + 1 := by
  simp only [eval] at h
  split at h
  · rename_i guard
    cases h
    exact ⟨guard.2.2.2.1, guard.2.2.2.2.1, rfl, rfl⟩
  · simp at h

end Minyar
