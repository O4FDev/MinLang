# Preregistered same-budget retirement experiments

4 October 2026. These are test-only hypotheses, not accepted runtime policies
or novelty claims. The generated 65-member retired-batch program establishes a
causal target: a last queued owner keeps a caller Text physically shared at a
consuming join, and an extra single K batch does not reach it even at K32.
Source evidence and controls are in `runtime-deferred-reuse.md`.

## Relocate existing allocation service before uniqueness

Hypothesis: on an owning Text that is physically shared with pending retirement,
moving the copy fallback's existing data/header allocation service earlier can
reconcile a dead owner before choosing copy versus reuse. Current fallback has
two separate allocation service hooks of at most K each; subsequent release has
its own allowance. One K batch at entry is insufficient in the generated
negative case, while the two existing allocation batches may reach its last
owner. That is a hypothesis to measure, not an established positive result.

The experiment must suppress the corresponding later allocation hooks, so it
relocates work rather than adding two more K batches. Explicit scoped allocation primitives in a copied runtime isolate the causal effect.
The actual fixture uses no global suppression flag.
It is not a proposed production architecture. Both arguments must retain the
compiler/runtime's existing lifetime protection during early service; no scan
may infer that an arbitrary high reference count is entirely dead ownership.
Overflow/evaluation checks must precede any newly moved service.

Preregistered observations and controls:

- Identical generated workload at K1/K8/K32; count every immediate destruction
  and queued unit across the **compound join**, not only the last poll counter.
  Keep per-allocation K and the sum of separate operation allowances distinct.
- Genuine live alias, flattened view, self RHS, unknown UTF-8, malformed UTF-8
  and already-unique paths. Equality/length alone is insufficient for Unicode.
- Opposite priority: a large first child and soon-reused last child, then the
  inverse, including workloads that never reuse the target Text. Record both
  target benefit and older-task progress under continuing arrivals.
- Data/header allocation failure injection, finite fixed/lazy pool admission,
  fragmentation, large spare capacity and late-arriving debt. Relocation can
  change failure ordering even if total cleanup work stays within old maxima.
- Header and backing reuse, copied bytes, requested/rounded peak and post-join
  storage, cache/frame retention and eventual quiescent drain. A reclaimed
  target owner can still leave an oversized retained backing.

Reject if correctness/lifetime/budget controls fail, if one-sided target gains
hide adverse admission or memory costs, or if maintaining the suppression and
transaction invariants requires more complexity than a representative gain
justifies. Retain negative outcomes. No hard latency follows from fixed work.

## Constant-work retirement ordering control

As a causal comparison, a copied runtime can reverse a dead reference List's
field index (`length−1−cursor`) while preserving one visit per unit, existing
cursor storage and queue fairness. This could visit the generated last owner
early with no extra scan or metadata. The opposite-order workload is mandatory:
the same policy may delay a large first child and harm retention/admission.
Nested cascades, recent versus captured lists and continuously arriving frame/
temporary tasks must preserve eventual service.

This reverse-order control is not compiler informed, and familiar LIFO/locality
policies are clear prior-art domains. A later compiler-informed experiment would
need a concrete existing liveness/reuse fact and a small internal encoding;
merely preferring the last field does not establish novelty or soundness.
Any result requires literature falsification before a contribution claim.

## Separation from a pure metadata candidate

Known-ASCII propagation in borrowed `join_by_copying` is a separate engineering
hypothesis: it can avoid subsequent ASCII length/index scans while preserving
all allocation and retirement service points. It must use certified character/
byte counts, keep Unicode unknown until rebuilding, and retain no extra header
or buffer. Its results must not be attributed to a retirement-order mechanism.


## Executed equal-credit causal and admission experiments

The research-only helper in `tests/memory-research-credit-relocation.h` moves two distinct existing K allocation hooks only when the initial owning Text is physically shared and pending retirement exists. Already-unique paths remain unchanged. It allocates/resizes through explicit no-service helpers after paying those hooks and retains the original fallback consuming-release allowance. Both arguments retain real owned/borrowed protection; overflow is checked before moved service. This duplicates runtime allocation code in a test snapshot and is not an acceptable production abstraction by itself.

[Four causal builds](evidence/runtime/results/credit-causal-counts.json) cover system/fixed K1/K32, nine cases and two policies: 72 observations. Near retired frame owners reconcile and enable header/backing reuse, while far owners still copy and live aliases/views preserve their old bytes. Self joins, Unicode indexing and already-unique spare/growth controls pass. Per-hook offered budget is at most K, destruction count is no larger than consumed queued plus immediate units, and the prototype's offered-plus-immediate allowance is never greater than the baseline's. This establishes the measured paths, not a general compiler lifetime or admission theorem.

At fixed/K32, the near case removes one data and one header allocation and 32768 copied prefix bytes. It consumes two queued units instead of the baseline's two queued plus one immediate unit. However, requested live bytes after the join increase from 32884 to 65650 because reuse retains spare capacity. Peak requested bytes during that join decrease from 98476 to 65650, and peak pool charge decreases from 197920 to 132320. Lower transient peak and higher persistent retention are separate observations.

The [finite-pool native counterexample](evidence/runtime/results/credit-admission-native.json) and [ASan+UBSan replay](evidence/runtime/results/credit-admission-sanitizer.json) use the same 524288-byte pool layout, native Text payload length 32768, original backing capacity 65536, immutable RHS, frame retirement and next managed data request 131060. Controlled 32-byte fillers hold the rest of the heap; they are an allocator-admission adversary, not a representative application distribution. Baseline copy compacts result capacity to 32770 and frees the old charged 131072-byte block. It succeeds on the next request and completely recovers the pool. The prototype reuses the original capacity 65536/charged 131072 backing; its unused output hole is only 65536 bytes and the same next request fails. Result bytes and logical length are identical; budgets do not increase. All fixed/lazy K1/K32 native and sanitizer cases reproduce this outcome (four builds/eight processes per matrix).

The initial [diagnostic-classifier attempt](evidence/runtime/results/credit-admission-classifier.json) already contained the successful baseline and expected prototype exhaustion, but the runner expected the generic OOM message instead of the bounded-heap exhaustion message. It is preserved as a classifier failure, not a runtime defect. The exact expected diagnostic was corrected before the full native and sanitizer matrices; no allocator or workload threshold changed.

Decision: reject this prototype as a default policy. These data disprove that its equal-credit reuse improvement necessarily preserves allocation admission; they do not prove all relocation or smaller-capacity schemes impossible. No production service schedule or ownership order changed. The causal improvement is engineering evidence and not a novelty claim: lazy RC before reuse/getrc, parent edges preventing uniqueness, LIFO zombie traversal and bounded allocation-triggered destruction have close precedents in the campaign literature review. A distinct contribution would require a precise admission/retention relation or a better supported policy, beyond these observations. The originally proposed generated 65-member same-credit case and reverse-order comparison have not yet been executed; no generated equal-credit result is claimed.

Closest-prior-art inspection and its exact review limits are recorded in [literature-fixed-credit-reuse.md](literature-fixed-credit-reuse.md); its primary links/section dispositions distinguish fully read papers, partial source inspection and inaccessible full texts. The experiment does not convert that bounded search into an exhaustive novelty result.
