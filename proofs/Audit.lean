import Lean
import Main

/- Every logical declaration receives the same axiom audit. Source unsafe/partial
   declarations reject. Lean's unsafe backend artifacts are counted separately
   only when they have a recognized implementation name AND no exact source
   declaration range. They contain erased compiler primitives such as lcProof;
   the logical kernel cannot use these unsafe implementations in a proof. -/

open Lean Elab Command

elab "#audit_minyar" : command => do
  let env ← getEnv
  let allowed : Array Name := #[``propext, ``Classical.choice, ``Quot.sound]
  let modules : Array Name := #[`Minyar, `Minyar.Ownership, `Minyar.Dma,
    `Minyar.Typing, `Minyar.Reclamation, `Minyar.Uniqueness,
    `Minyar.Finite, `Minyar.Language, `Minyar.Effects,
    `Minyar.Contract, `Minyar.Examples, `Main]
  let mut declarations := 0
  let mut theorems := 0
  let mut selected : Array ConstantInfo := #[]
  for moduleName in modules do
    unless env.header.moduleNames.contains moduleName do
      throwError "foundations module was not imported: {moduleName}"
  for (name, info) in env.toKernelEnv.constants do
    let ownModule := match env.getModuleIdxFor? name with
      | none => false
      | some index => (env.header.moduleNames[index.toNat]?).any modules.contains
    if ownModule || (`Minyar).isPrefixOf (privateToUserName name) then
      declarations := declarations + 1
      selected := selected.push info
  -- Stable diagnostic categories regardless of generated-helper iteration order.
  let mut partials : Array Name := #[]
  for info in selected do
    if info.isPartial then
      partials := partials.push info.name
  unless partials.isEmpty do
    throwError "partial declarations in foundations: {partials}"
  let mut unsafes : Array Name := #[]
  let mut implementations : Array Name := #[]
  for info in selected do
    if info.isUnsafe then
      let exactRange ← findDeclarationRangesCore? info.name
      let implementationName := ["_cstage", "_spec_", "_closed_", "._at.",
        ".match_", "_lambda_", "_elambda_"].any fun marker =>
          decide ((info.name.toString.splitOn marker).length > 1)
      if exactRange.isNone && implementationName then
        implementations := implementations.push info.name
      else
        unsafes := unsafes.push info.name
  unless unsafes.isEmpty do
    throwError "unsafe declarations in foundations: {unsafes}"
  for info in selected do
    if info matches .thmInfo _ then theorems := theorems + 1
    unless implementations.contains info.name do
      let axioms ← collectAxioms info.name
      for axiomName in axioms do
        unless allowed.contains axiomName do
          throwError "unapproved axiom {axiomName} in foundations declaration {info.name}"
  unless theorems > 20 do
    throwError "unexpectedly small proof surface: {theorems} theorems"
  logInfo m!"foundations audit: {modules.size} modules, {declarations} declarations, {theorems} theorems; axioms restricted to propext, Classical.choice, Quot.sound"
  logInfo m!"foundations logical declarations: {declarations - implementations.size}; generated implementations: {implementations.size} unsafe backend helpers without exact source ranges, excluded from logical axiom audit"

macro "audit_foundations" : command => `(#audit_minyar)

#audit_minyar
