# G14 independent review R1

Task: node:delegated-task:command%3Amcp%3A171c7d67-2624-4bef-adfa-9535fd35be0b%3Adelegate-task%3Aws2-g14-independent-review-r1-6956b3d-20261012

+**REQUEST CHANGES — `6956b3df044270b62af6356b4aa99ed35ce276cb`.**

- **[P1] Error reporting can turn recoverable depth exhaustion into process termination.** [minyar_calldepth.h:64](/Users/luke/.t3/worktrees/Minyar-Lang/ws2-g14-review/runtime/minyar_calldepth.h:64) routes reporting entries through ordinary `minyar_stack_enter()`, which still traps at the global/fallback cap. After an inner scope ends, [calldepth-compiler.min:71](/Users/luke/.t3/worktrees/Minyar-Lang/ws2-g14-review/compiler/calldepth-compiler.min:71) invokes guarded result factories while the restored parent remains near that cap.

  Independently reproduced with small native C checks:
  - `MINYAR_MAX_CALL_DEPTH=2`: main plus outer callback reach depth 2; inner callback rejects; reporting exits 1.
  - Unknown bounds with fallback 16: reporting exits 1 at depth 16 while `remaining()` is **85**.
  - Archived `nested.O0.ll`, linked against the exact candidate runtime with maximum 4, also exits 1.

  All emit `Minyar stopped: the program exceeded the maximum call depth.` Reporting needs reserved headroom or propagation to a safe outer boundary while preserving physical stack guards. Add regression coverage for both caps. The physical-reserve variant remains unverified.

**WS1 composition requires an unwind hook.** [build-calldepth-compiler.py:75](/Users/luke/.t3/worktrees/Minyar-Lang/ws2-g14-review/compiler/build-calldepth-compiler.py:75) synthesizes accepted unwind with only RC/depth leaves. Any WS1 entry/return bookkeeping needs a matching G14 hook or subsequent composition pass; rejected entries must bypass accepted-entry cleanup. Linked WS1 behavior is unverified.

Evidence checks passed: all 1,343 archived source hashes, candidate comparison except the documented TLS test overlay, 25 prior manifest input audits, 21 final checks, and 659 independently checked recorded outputs. The recovery frontend/fixed-point bytes match. Five representative LLVM modules parsed successfully; checkpoint, cleanup, domain-order and PHI audits found no additional defect. The original neo-db repro’s fatal behavior is preserved.

Only exported artifact bytes were independently hash-verified; absent binaries remain hash records. Full platform, ≤1% application-performance, WS1 linking and G15 composition gates remain pending.

The detached review tree is clean at `cf2c26279cd8c21a766574ca55d39c4c5a3c94a6`. No candidate edits or host operations were performed.
