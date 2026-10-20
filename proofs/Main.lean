import Minyar

namespace MinyarChecker

open Minyar

def parseEffect : String → Option Effect
  | "scalar" => some .scalar
  | "mmio" => some .mmio
  | "signal" => some .signal
  | "managed" => some .managed
  | "float" => some .float
  | "blocking" => some .blocking
  | "lock" => some .lock
  | "native" => some .native
  | "indirect" => some .indirect
  | "cyclic" => some .cyclic
  | _ => none

def parse : List String → Option Command
  | ["alloc", object, slot, scope] => do
    return .heap (← object.toNat?) (.alloc (← slot.toNat?) (← scope.toNat?))
  | ["retain", object, source, target, scope] => do
    return .heap (← object.toNat?)
      (.retain (← source.toNat?) (← target.toNat?) (← scope.toNat?))
  | ["move", object, source, target, scope] => do
    return .heap (← object.toNat?)
      (.move (← source.toNat?) (← target.toNat?) (← scope.toNat?))
  | ["borrow", object, source, target, scope] => do
    return .heap (← object.toNat?)
      (.borrow (← source.toNat?) (← target.toNat?) (← scope.toNat?))
  | ["endborrow", object, slot] => do
    return .heap (← object.toNat?) (.endBorrow (← slot.toNat?))
  | ["use", object, slot] => do
    return .heap (← object.toNat?) (.use (← slot.toNat?))
  | ["release", object, slot] => do
    return .heap (← object.toNat?) (.release (← slot.toNat?))
  | ["reuse", object, source, target, scope] => do
    return .heap (← object.toNat?)
      (.reuse (← source.toNat?) (← target.toNat?) (← scope.toNat?))
  | ["exit", object, scope] => do
    return .heap (← object.toNat?) (.exit (← scope.toNat?))
  | ["submit", object, slot] => do
    return .heap (← object.toNat?) (.submit (← slot.toNat?))
  | ["retire", object, slot] => do
    return .heap (← object.toNat?) (.retire (← slot.toNat?))
  | ["irq_enter"] => some .irqEnter
  | ["irq_exit"] => some .irqExit
  | ["effect", effect] => do return .effect (← parseEffect effect)
  | _ => none

def words (line : String) : List String :=
  (line.trim.splitOn " ").filter fun word => word != ""

/-- The input limit makes the IO driver total and fails closed on oversized traces.
    Parsing and IO are outside checker_sound; every parsed command calls step. -/
def readCommands (fuel : Nat) (world : World) (line count : Nat) : IO UInt32 := do
  let mut current := world
  let mut currentLine := line
  let mut accepted := count
  for _ in List.range fuel do
    let input ← (← IO.getStdin).getLine
    if input == "" then
      IO.println s!"ok {accepted}"
      return 0
    let trimmed := input.trim
    if !(trimmed == "" || trimmed.startsWith "#") then
      match parse (words input) with
      | none =>
        (← IO.getStderr).putStrLn s!"error line {currentLine}: parse"
        return 1
      | some command =>
        match step current command with
        | none =>
          (← IO.getStderr).putStrLn s!"error line {currentLine}: rejected"
          return 1
        | some next =>
          current := next
          accepted := accepted + 1
    currentLine := currentLine + 1
  (← IO.getStderr).putStrLn s!"error line {currentLine}: input limit exceeded"
  return 1

end MinyarChecker

def main : IO UInt32 := MinyarChecker.readCommands 1000000 Minyar.initialWorld 1 0
