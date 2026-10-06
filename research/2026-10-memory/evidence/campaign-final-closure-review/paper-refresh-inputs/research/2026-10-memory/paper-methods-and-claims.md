# Admission, metadata, and local cleanup demand in an incremental reference-counted runtime

This methods and contribution brief supports eventual paper development. Its defensible contributions are concrete admission counterexamples, a conditional transformation argument, representation-preserving production repairs with measured tradeoffs, and a narrow implemented local-demand analysis. It is not a finished PhD paper. **Novelty is unestablished:** reserve, bulk copy, ASCII certificates, reference counting, and potential-based resource inference are prior art. Campaign acceptance remains with the coordinator; the earliest finish is 2026-10-04T06:54:29Z.

The [claims ledger](paper-methods-and-claims.json) binds every claim below to complete SHA-256 identities and copied inputs. Labels distinguish **accepted scoped** executed evidence, **conditional** source arguments, **rejected** generalizations/candidates, **inconclusive** outcomes, **proposed** hypotheses, and **pending** dispositions. Hash checking establishes artifact identity, not semantic correctness.

## Candidate abstract

Automatic ownership management can preserve values and bounded cleanup allowances while changing whether a later allocation succeeds. We examine this distinction in Minyar's incremental reference-counted runtime without adding language syntax. Saved experiments show admission failures from unconditional preallocation, buffer slack, and relocation of existing cleanup service. A reviewed conditional argument relates direct and geometric fresh scalar construction in a canonical finite buddy pool; finite replays inspect ordered allocator state. Truthful ASCII metadata avoids redundant scans, while a Unicode consuming-join repair demonstrates why numerical character counts alone are insufficient certificates. We distinguish structural cleanup from storage and show that two Text owner orders require three versus four units. A standalone research analyser derives a conditional four-unit local demand from thirteen selected definitions in actual generated LLVM, with external borrower protection unresolved. Independently audited primitive measurements retain benefits and adverse controls. These results motivate refinement and composition research; they establish neither a novel collector nor universal memory, admission, or latency guarantees.

## Questions and falsifiable hypotheses

The central question is which transformations preserve observable values, owner protection, structural service, and finite-pool admission together. These are distinct obligations. **RQ1:** under what state restrictions can allocation opportunities be removed safely? The broad hypothesis that equal values or equal offered credit suffices is rejected (C01–C04). The narrower fresh-scalar buddy relation survives its stated source audits and finite controls (C02).

**RQ2:** can existing metadata certify avoided work without weakening representation validity? The hypothesis survives only for truthful ASCII certificates and protected operands; unknown or indexed Unicode must stay conservative after index invalidation (C05–C06). **RQ3:** can local cleanup demand be inferred from actual owner transfers without new syntax? A selected subset is implemented, but general caller composition remains proposed (C07–C08, C14). Reject composition on an omitted escaping producer, unprotected borrow, hidden ownership effect, or wrong branch proof; retain conservative rejection rather than extending the grammar to obtain a pass.

## Resource definitions and method

An individual cleanup unit is a reported owner/aggregate-position visit or a separately charged task finalization; inline leaf death can be cocharged with a visit. The configured budget K limits the specified service mechanism. A source expression can invoke several hooks, and helper/direct polls must be distinguished to avoid double-counting nested work. Copies, initialization, UTF-8 scans, allocator metadata, system calls and total elapsed time are separate resources.

Requested managed bytes exclude some raw/frame/cache storage. Pool charge instead sums rounded block classes, including simultaneous old/replacement storage. Retained capacity, live logical payload and cached storage require separate accounting. Contiguous admission means the actual allocator can satisfy a particular request in its current placement state; sufficient total free bytes is insufficient. End-of-epoch requested-byte maxima, periodic RSS samples and completed child high-water RSS measure different things.

The scientific method combines independent semantic oracles, requirement-first failures, source arguments and saved finite execution. A failed allocation/scan requirement is a work red, distinct from a semantic defect. Baseline-green coverage, oracle mutants, parser failures, setup failures, and resource aborts keep their actual classifications. Counterexamples use deliberately controlled histories to test causal mechanisms, not a sampled application distribution. Independent reviewers inspected transitions, probes, source identities and measurements. This synthesis ran only document and hash checks: no new experiment, compiler, native program, statistical estimate, or timing acquisition.

## Allocation and service order

Unconditional known-size List reservation eliminates growth hooks that can reclaim an upper buddy before the final request. Saved fixed/lazy pressure cases exhibit baseline success and candidate exhaustion. An object-only debt guard also misses detached frame/chunk work. The accepted guard tests **all pending tasks after common header creation**, preserving the old growth schedule whenever debt remains (C01).

Bytes slack supplies a different history boundary: debt is created after an idle capacity choice. The seventeenth append then fits without growth/service; saving 32 backing bytes leaves a retired 1024-byte block unavailable to the next raw path allocation (C03). Moving two existing K allocation services before uniqueness can avoid a 32,768-byte prefix copy, yet reuse retains a 131,072-byte backing block. Baseline's compacted copy admits the subsequent 131,060-byte request; the relocated-service candidate fails in the controlled 524,288-byte pool (C04). These negatives reject those candidates, not every capacity or service policy.

For C02, define a valid canonical buddy pool with minimum block 32 and capacity 32·2^D. Decision state contains the complete map, allocated boundaries, every ordered free-list node with both links, mask and current charge. The relation also preserves initialized semantic payload and ownership/scheduler/cache state; it excludes telemetry, spare/free bytes, padding and sanitizer/OS state.

The reviewed argument assumes matched valid states; the supported 64-bit fixed, non-arena ABI; successful identical common header service/allocation; zero all-task debt afterward; a protected, initialized scalar source and identical scalar tail; fresh NULL destination backing; representable capacity and header-inclusive arithmetic; an adequate original final-class free block; one mutator, no reentrancy or intervening operation; truthful owner/queue invariants; and legal continuations that track live initialized extents, valid resize-copy ranges and ownership without consulting excluded state. Direct reservation and geometric construction then restore the same ordered decision state and initialized result, supporting equal success/address responses for legal raw continuations. The induction restores departed regions before their original list tails. It is a mathematical argument with reviewed source correspondence, not verified whole C/LLVM.

Finite length-3/7 and adapted unsorted length-15 replays inspect full maps/links and selected continuations. They corroborate correspondence without proving the induction. High-water differs in the length-3 case, 192 versus 160 bytes; literal whole-state equality is false. Debt, reference effects, existing backing, failed constructions and system/lazy allocator equivalence are outside this theorem. Idle polls are inert in the relation; `rc_step` can detach active temporaries before polling.

## Metadata as a local certificate

In the supported Text representation, known character count with NULL offsets certifies ASCII. Consuming indexed `é🙂` into `é🙂xy` previously retained a correct numerical length while character zero became U+00C3 instead of U+00E9. Invalidating non-ASCII metadata after discarding offsets repairs Character and slice access (C05). A proposed Unicode-view count shortcut is rejected by source consumers; it has a hand counterexample, not a new executed red.

Borrowed-copy and aggregate joins preserve counts only when every operand's truthful character count equals its byte length. Protected operands, valid visible byte extents, representable arithmetic, supported constructor/mutation invariants, single-mutator nonreentrancy and valid C/library execution are premises. NUL, certified empty values and certified views fit; Bytes capacity, forged native headers, unknown and indexed Unicode do not certify ASCII. The aggregate patch adds checks in the existing sizing pass without changing requests, copies or service order. Refined all-poll events qualify older helper-only observations (C06).

## Conditional cleanup demand and implemented inference

Let V count remaining physical visits, including sparse moved/null frame positions and reference-record scalar positions; F count separately finalized nonempty reference aggregates, heap-frame activations and chunks; Q count queued owning Text roots; and R count live mortal owning Text roots once per identity. Scalar leaves and views add no separate finalizer. For a closed continuation σ, δ(r,σ) is one when the last owner of root r disappears through a view, otherwise zero:

```text
W(σ) = V + F + Q + Σr δ(r,σ)
V + F + Q ≤ W(σ) ≤ V + F + Q + R.
```

C07 assumes finite acyclic supported 64-bit non-arena ownership; truthful, representable counts/tags/cursors/Text metadata; protected borrows; one mutator and no reentrancy, user finalizers or weak owners; valid queue/owner conservation; complete initialized roots in frames/chunks at the boundary; no in-flight producer/foreign root or immortal container hiding mortal children; faithful branch-sensitive C-to-ticket correspondence including fused carried children; valid stack-storage lifetime; and subsequent matched retirement plus fair positive full service without new allocations, owners, mutation, indexing or cache growth. Direct external releases are excluded; step is detachment, not idle polling. Cache disposal is outside W. A maintained ledger requires a uniform supported managed universe from inception: selectively excluding intermingled Text/Bytes is unsupported because their leaf representation is indistinguishable.

The native tiny Text root/view control observes **3 versus 4 units** with identical aggregate V/F/Q/R and allocation multiset, solely by reversing local-owner order. Automatic leave work is included. Exact prediction from those aggregates alone is rejected; the conditional interval survives. Work does not bound bytes, admission or seconds.

C08 is a standalone Python parser/body/loop/ownership experiment over actual saved `textures.snow` LLVM: **13 selected definitions, 225 instructions, 29 blocks, loop bound 2; V=2/F=2/W=4 after full service**. Two fresh scalar Lists occupy one chunk; the frame supplies the other finalizer. The analyser derives effects and owner transfers, not a stored answer. External Bytes protection remains `required_not_discharged`; the actual caller retains and returns Bytes. Trusted frozen runtime summaries, successful allocation/arithmetic/bounds/guard execution, fresh separation, truthful protected external representations, exact linking/scalar semantics/optimizer preservation and fair eventual service remain premises. C/LLVM refinement and compiler build attestation are unresolved. No at-return or global certificate follows.

Author tests exposed parser/dataflow bugs; independent review found three false accepts in e149: parallel branch arms, numeric SSA identity, and Float labels. Conservative subset exclusions repaired d260. Saved validation has **131 assertion groups: 20 positive/111 rejection, 118 input hashes**, plus unchanged independent **5/5 probes**. Seven historical fault families and four affected/new controls overlap; they are not eleven unique families. These results validate a narrow implemented experiment, not general automatic memory management.

## Production value, tradeoffs and validation scope

C09's separate production-config scalar cohort has 204 pilots and 192 adjacent randomized pairs/384 measured children. Its native O2 timed source contains the isolated scalar patch with the earlier c4 runtime. Large system/fixed 1024/8193 cases have baseline/candidate geometric ratios **2.34–2.46**, with pointwise paired intervals. Fixed empty/reference retain approximately **0.967%/1.035% higher candidate CPU**; all 41 adverse pairs remain. Clocks include append, opaque full-value checksum, release/drain and control debt setup, not pure copying. The earlier 192-pair test-accounted cohort remains separately corrected/audited; bookkeeping cannot be cancelled across cohorts.

C06's aggregate 4096-byte five-fragment case has ratio **2.480824 [2.464376, 2.498152]**; unknown/no-query retain about 1.1%/0.5% adverse points. Its constructor/destructor process clock includes setup/output/ownership work and excludes a separately measured final drain. Borrowed ASCII's 2.392 median and adverse no-query observations are another estimator/workload. No pooled gain, added-byte benefit or application speed claim follows.

Final d919 runtime/3b collections preserve exact reviewed patches without formatter differences. C10's separate focused scopes are List 24 native/21 generated plus seven immutable generated-ASan supplements; scalar 34 shapes in three configurations; pressure 16 builds/48 executions; bits six executions; aggregate 18 generated/six native debt/two traps; Text 21 C/21 generated/21 traps; caller five generated/three native plus a revised 55-line baseline; two Text projections six each; and three archive-only native boundaries. These units are not summed.

Both earlier 7200-second cohorts pass on c4/01ae and exclude the new paths (C11). C12's final-source 1800-second native correctness endurance is **running/pending** in the captured record. Short native/C sanitizer pilots and two oracle calibrations passed. Intentional test accounting, nonallocating copy observation and 5% batch pacing make this correctness endurance, not speed evidence. No long pass is inferred.

## Predecessors, validity and next proof

[Lam–Parreaux CTRC](https://lptk.github.io/files/ctrc-2024-05-09.pdf), Appendix A Lemmas 1–3/Theorem 1, already relates lazy/eager counting and bounded uniform-cell instructions. Its constant-cost statement abstracts fresh system allocation and omits compiler segmentation refinement; it does not prove Minyar variable-block admission. [Yue Niu–Hoffmann](https://www.cs.cmu.edu/~janh/assets/pdf/NiuH18.pdf), §§4–5 and Appendix D, already provides collector-sensitive AARA with sharing/continuation simulation. Its ideal free-cell semantics abstracts fragmentation and mutable identity. These are predecessor comparisons, not imported proofs. Round-three reviewers read the complete 30/45-page author artifacts; this synthesis reread selected proof/model passages. Missing/abbreviated Niu proof cases remain recorded; proceedings equivalence is unverified. The older 51-source register is mixed-depth, not exhaustive literature.

Internal threats include trusted runtime/library/compiler summaries, observer perturbation, changed oracle/harness versions and nonhermetic build provenance. External/statistical threats include one loaded host, twelve pairs per case, exploratory preparation, unverified exchangeability, pointwise bootstrap intervals, capped aggregate pilots and the recorded missing child CPU limit. No statistical significance, calibrated joint confidence or asymptotic superiority is asserted.

Peer evidence supplies breadth: 646 heterogeneous groups/30 selected files and thirteen original projection methods/78 historical selected executions, not full ports or a final full suite. Native repairs and tiny GL pixel controls supply practical context. The real 20 MiB world passes O2, but its sanitizer invocation is resource-aborted above 128 MiB without complete output/diagnostic; it is inconclusive (C13). Full game/GPU/HFT readiness is unestablished.

Reproduction scopes follow the exact retained fixture/runner/source/result manifests. Selected native boundaries require installed Darwin Clang/SDK; generated studies require the identified compiler/LLVM/toolchain. This brief copies claim anchors, not every original archive or executable. Hashes do not attest source-to-binary builds. No final broad integration/coverage, generated UBSan or LSan claim follows; the blocked access question remains unanswered. The certifier's frozen c4 catalog does not certify d919.

Prioritize formal C/LLVM/library and caller-closure refinement; independent quiet-host workload/tail studies with declared arrival protocols; final broad integration when available; and larger real-application coverage. C14 proposes compositional owner-demand/admission criteria that preserve existing counterexamples, protected callers and unchanged syntax. Each requires a separate proof and falsification protocol; no publication or campaign completion is implied.

## Evidence and claims ledger

Complete hashes, assumptions, primary attribution and exact reading extents are in [the machine ledger](paper-methods-and-claims.json), [reading ledger](../../evidence/paper-methods-and-claims/reading-ledger.json), and [documentary checks](../../evidence/paper-methods-and-claims/documentary-checks.json). The following IDs are the claim keys above; result prefixes are labels only, with full immutable SHA-256 values in JSON.

| ID | Status | Principal anchor and scope |
| --- | --- | --- |
| C01 | Accepted scoped / rejected candidate | Object/frame/chunk debt records; guarded reservation report; final List gate `c0dc6494…`. |
| C02 | Conditional / finite executed evidence | Transformation/admission audits; hand results `1ecc4a0e…`, `d880d74b…`; excludes telemetry. |
| C03 | Rejected | Bytes policy result; eight original/candidate fixed/lazy O2/C-sanitizer processes. |
| C04 | Rejected | Equal-credit causal/admission native and C-sanitizer records; no generated relocation claim. |
| C05 | Accepted scoped / rejected shortcut | Unicode native/generated reds, view source rejection, final Text `ad1a17ea…`. |
| C06 | Accepted scoped / conditional invariant | ASCII counters, refined aggregate events, aggregate timing `d1000f83…`, independent performance audit. |
| C07 | Conditional / accepted tiny observation | Demand/audit premises; Text root/view result `a1bd5151…`. |
| C08 | Accepted research subset / conditional result | Exact d260 checker/c4 catalog, certificate, green records, e149 and repaired independent probes. |
| C09 | Accepted scoped | Production-config scalar result `d5395851…` and independent review; isolated timed tree. |
| C10 | Accepted focused scopes | Joint result `1b9e80d0…`, every linked gate, review checkpoints and own-patch reconstruction. |
| C11 | Accepted scoped | Fixed `40df9f59…`, system `9481abd2…`; pre-adoption c4/01ae. |
| C12 | Pending | Running final-source record snapshot `b5772e47…`; pilots `f5674bc6…`. |
| C13 | Accepted context / inconclusive | Peer provenance; world O2 `d1389c72…`, retained abort disposition, tiny GL baseline `959563a5…`. |
| C14 | Proposed / novelty unestablished | Primary CTRC/AARA artifacts and reading-depth reports; no new execution. |
