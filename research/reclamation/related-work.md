# Initial related-work comparison

Reviewed 2026-09-20. This is a targeted reading, not an exhaustive novelty search.
Differences below are hypotheses to investigate, not claims of priority.

## Closest direct comparison

Lam and Parreaux, *Being Lazy When It Counts: Practical Constant-Time Memory
Management for Functional Programming*, FLOPS 2024.
[Author manuscript](https://lptk.github.io/files/ctrc-2024-05-09.pdf),
[DOI](https://doi.org/10.1007/978-981-97-2300-3_11).

Sections 2.1–2.4 and Appendix A describe lazy reclamation integrated with uniform
allocation cells, an implementation in Koka, and a formal space argument under
their model. Larger objects can be split. Section 2.5's EDA extension uses effects
to separate potentially expensive variable-size allocation from sensitive code;
it also segregates pending reclamation into two free lists. Their evaluation
compares against Koka/Perceus. Consequently, neither constant-time RC nor using
effects to isolate allocation is an available broad novelty claim for Minyar.

Minyar retains variable-sized contiguous Lists/records and explicitly bounds
traversal work, excluding allocation, copying, and OS effects. Candidate research
differences are fair service independent of future allocation, detached local
and temporary owner retirement, and compiler selection of stack ownership storage
based on the same budget. These differences need comparison with the full CTRC
implementation; the manuscript alone does not establish their absence there.
The pilot in this directory does **not** implement CTRC or compare against Koka.

### Follow-up implementation inspection

Inspected the authors' `koka-ctrc` repository at
`a99ecb8c1387123546d8f3bda8fc2bad8e36130e` (the default `locality` branch when
retrieved). In [`ctrc.c`](https://github.com/hkust-taco/koka-ctrc/blob/a99ecb8c1387123546d8f3bda8fc2bad8e36130e/kklib/src/ctrc.c),
`defer_drop` puts cells onto page-local lists; `pop_free` can process their
outgoing fields when allocation requests a cell. This gives a concrete
allocation-driven reclamation path to compare with Minyar's explicit polling.
In [`Parc.hs`](https://github.com/hkust-taco/koka-ctrc/blob/a99ecb8c1387123546d8f3bda8fc2bad8e36130e/src/Backend/C/Parc.hs),
`ownedInScope` computes per-variable drops and inserts them into the generated
expression. These inspected paths differ from Minyar's detachable owner tables;
that observation does not prove that no related mechanism exists elsewhere or
in earlier work. Nor does a default development branch identify the exact
published evaluation artifact. Frozen selected files and hashes are in
`build/reclamation-prior-art/`; no external code was executed or benchmarked.

## Older space and pause limits

Boehm, *The Space Cost of Lazy Reference Counting*, POPL 2004.
[Author presentation](https://www.hboehm.info/popl04/refcnt.pdf),
[publication record](https://research.google/pubs/the-space-cost-of-lazy-reference-counting/).

The presentation explains that lazy deletion and its variable-size space penalty
are longstanding, with lower bounds under stated assumptions. Minyar's finite
pool and work budget do not evade this tradeoff. Fairness of individual tasks
does not establish bounded retained bytes under ongoing allocation. Read the
full paper's assumptions before claiming a new space bound; this pass inspected
the author's slides rather than independently reconstructing that proof.

## Compiler ownership and reuse

Reinking, Xie, de Moura, and Leijen, *Perceus: Garbage Free Reference Counting
with Reuse*, PLDI 2021.
[Author publication and manuscript](https://www.microsoft.com/en-us/research/publication/perceus-garbage-free-reference-counting-with-reuse-2/).

Perceus supplies precise RC insertion, reuse, and formal guarantees for its core
language. Automatic retain/drop insertion, borrowed references, and uniqueness
reuse cannot be treated as new by themselves. Minyar deliberately permits
retired objects and owners to remain allocated between polls; it must not claim
Perceus's garbage-free property for that implementation. Compare compiler costs
and guarantees separately from collector scheduling.

## Acyclicity and stack reference optimization

Joisha, *Compiler Optimizations for Nondeferred Reference-Counting Garbage
Collection*, ISMM 2006.
[DOI](https://doi.org/10.1145/1133956.1133976),
[paper mirror](https://citeseerx.ist.psu.edu/document?doi=3a4282200f3937098e26199e3d52857b80b06b22&repid=rep1&type=pdf).

Section 3 and Figure 8 use a type connectivity graph to identify acyclic types
for specialized RC operations; stack-reference optimization is also central.
Minyar instead rejects certain mutations while allowing recursive immutable
construction. That use of a type graph may be a useful restricted design, but
the type-graph technique itself is established. The mirror was readable during
the initial assessment and failed to fetch on this follow-up; obtain a stable
full-text copy before completing the detailed comparison.

Lu and Potter, *On Reachability and Acyclicity*, UNSW-CSE-TR-0434, 2004.
[Institutional technical report](https://cgi.cse.unsw.edu.au/~reports/papers/0434.pdf).

The report develops region-parametric types and reachability constraints that
confine cycles to regions. Minyar's rule has fewer language features and requires
no user region declarations. Evaluate that simplicity against lost expressiveness;
do not claim that enforcing acyclicity using types is itself novel.

## Claim matrix

| Candidate claim | Current assessment | Evidence still required |
| --- | --- | --- |
| First incremental/constant-time RC | Already covered by prior work | Do not claim |
| New universal space bound | Unsupported, conflicts with known constraints if unqualified | Explicit assumptions and proof |
| Fair reclamation of objects, locals, and temporaries under a shared work contract | Plausible narrow contribution; priority unconfirmed | Broader historical search, formal model, actual adversarial traces |
| Budget determines eligible stack owner frames | Concrete compiler/runtime design point | Benefit versus fixed threshold/heap-only controls, related-work audit |
| Mutation rule gives simple annotation-free acyclicity | Possible supporting contribution | Soundness proof and rejected-program/expressiveness study |
| Critical-region effects alone are new | Already close to CTRC's EDA extension | A different, demonstrably useful guarantee |
| Good HFT latency | Existing local assessment does not support it | Deployment workload and target-host evidence |

Next bibliography work: follow CTRC's references to earlier lazy RC, read
real-time RC work including Ritzau, and examine root-processing/scheduling in
incremental collectors. Reference counting with frame-limited *reuse* is also
worth checking, but reuse and retirement of an activation's owners are different
operations. No title-level similarity or difference establishes novelty.
