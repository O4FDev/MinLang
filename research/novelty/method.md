# Minyar novelty review method

This document records the scope and limitations of the [assessment](review.md) completed on 3 October 2026. It accompanies the [source register](sources.md) and [local snapshot manifest](snapshot.json).

## Review question

Where could the whole Minyar language make a substantial, nontrivial research contribution, starting with its current bounded reference-counting work?

The review prioritizes contributions that can be stated as a useful theorem, a new algorithm with a meaningful guarantee, or a demonstrated tradeoff against the closest prior implementation. It gives low weight to syntax changes, implementation effort alone, and combinations of established features without an additional result.

## Search approach

This was a targeted narrative review with citation chaining and repeated attempts to find disconfirming work. It was not a preregistered systematic review. There is no exhaustive database export or deduplicated record of every search hit, so the register count must not be reported as the number of papers in the entire field or the size of a complete screening funnel.

Searches used the web tool and then primary author, publisher, institutional, proceedings, preprint, or official implementation sources. Secondary results helped locate papers and clarify bibliographic metadata, but do not support the technical judgments. Access failures were retained as limitations rather than silently replaced by assumed content.

The principal search families were:

| Family | Terms and citation chains used | Purpose |
| --- | --- | --- |
| Lazy and real-time RC | bounded reference counting; constant-time reclamation; RTRC; CTRC; space cost of lazy reference counting | Find close algorithmic and space precedents |
| Collector scheduling | real-time GC; time-triggered GC; allocation-driven cleanup; tax-and-spend | Test whether event service policies are already established |
| Automatic ownership | Perceus; Counting Immutable Beans; frame-limited reuse; FIP; ASAP; Morphic; Lobster | Test annotation-free ownership and allocation reuse claims |
| Resource analysis | AARA; automatic heap bounds with garbage collection; collector-sensitive lifetime analysis; prophecy potentials; persistent amortised analysis | Find source-level cost and space precedents |
| Reachability and capabilities | reachability and acyclicity; field-sensitive cyclicity; freshness; bidirectional reachability inference; flow-sensitive ownership; capture separation; modes | Evaluate permissive acyclic mutation and reuse evidence |
| Regions and representations | reference capabilities; LoCal; Marmoset; SoCal; LoCalMem | Evaluate automatic layouts and boundary accounting |
| Reactive programs | bounded-space FRP; RaTT; sized embedded reactive datatypes; asynchronous modal types | Compare guarantees for ongoing programs |
| Concurrent and cyclic collection | ORCA; concurrent immediate RC; arborescent GC | Identify why simply adding actors or cycles is insufficient |
| Compiler guarantees | Alive2; CerCo; combining source and target costs; performance and compile-time guarantees; incremental builds | Evaluate cost preservation and predictable inference |

Representative exact follow-up queries included:

```text
"Decreasing Memory Overhead in Hard Real-Time Garbage Collection" Ritzau Fritzson
"Fully-Automatic Type Inference for Borrows with Lifetimes" pdf
"Higher-Order Functional Reactive Programming in Bounded Space" POPL 2012
"Optimizing Layout of Recursive Datatypes with Marmoset" paper
"LoCalMem:"
"Type-Directed Adaptive Serialization"
"Build Systems à la Carte" 2018 paper
```

Recent results were checked against publication/version dates where accessible. In particular, Morphic's borrow inference is published in OOPSLA1 April 2026; several other 2026 works are preprints. Capture Now, Consume Later changed title from an earlier version. Search crawl dates were not treated as publication dates.

## Evidence inclusion and reading depth

The source register includes directly relevant foundations, close alternatives, useful disconfirming results, official implementation documentation, and a small number of inaccessible but important records. It deliberately records mixed reading depths. An F entry means relevant full-text sections were inspected, not that a full formal proof audit was performed.

Hypotheses about missing capabilities are qualified where a comparison was based on an abstract. The review does not infer that a paper lacks a property merely because its abstract does not mention it. Source-specific performance results are not projected onto Minyar.

Primary-source links were opened or located during the review. Links with failed access are still included when they identify a legitimate publication, and their reading depth records the limitation. The saved report's local links were checked for existence; final browser rendering and future availability of remote sites are separate concerns.

## Local Minyar evidence

The review inspected the language, runtime, bounded-contract, architecture, performance, and incremental-build documentation. It also inspected the existing reclamation model, related work, pilot results, follow-up assessment, and prospective acceptance suite. Selected compiler/runtime files were used to check where the current ownership and representation decisions live.

The working tree was dirty before the review, including compiler/runtime changes and untracked research files. This review adds only the new novelty directory. It neither resets existing work nor treats the repository commit as a complete description of the reviewed state.

The snapshot manifest contains SHA-256 hashes and byte lengths of selected local inputs. It is an identification record, not a complete reproducible source archive. Reproducing old runtime measurements still requires their retained binaries, LLVM, commands, traces, and environment manifests. Those ignored build artifacts can be removed by ordinary cleaning.

No new runtime benchmark or compiler regression campaign was performed for this review. Numerical statements about Minyar's prior experiments are attributed to the existing assessments. Those assessments explicitly limit their coverage; the review preserves those limits.

## Criteria for proposed directions

Each direction was evaluated for fit with current semantics, closeness of prior work, a possible precise claim, an identifiable proof obligation, an informative experiment, and a plausible condition that would rule it out. Rankings are judgment, not publication probabilities.

Shared observable mutation, compiler-generated ownership, deferred descendant cleanup, stack storage validity, and variable-sized capacity are treated as separate constraints. A comparison that changes one of them must say so. An abstract work-unit bound is not reported as a hardware deadline.

The proposed experiments are future work. No success, effect size, theoretical novelty, or expected publication outcome has been fabricated. A theorem under useful assumptions can be a contribution even when the implementation does not dominate every baseline on every metric.

## Remaining priority audit

The highest-value missing full texts are the Boehm paper, frame-limited reuse, Morphic, collector/lifetime-sensitive heap analysis, Joisha, the latest ownership-transfer reachability paper, GhostCell, LoCal, and LoCalMem. Their absence weakens exact priority claims, especially for directions 1–4.

Further chaining should cover region inference, shape/escape analysis, collector root scheduling, WCET and real-time Java, and incremental static analysis. A formal submission should repeat the search with its final precise theorem and target assumptions, rather than cite this exploratory review as proof of absence of prior work.
