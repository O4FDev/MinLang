# Minyar novelty review sources

This register supports the [research assessment](review.md). Searches and access checks were conducted on 3 October 2026. Publication dates below refer to the work, not a search engine crawl date. Recent preprints are marked separately from published papers. The register includes useful negative evidence and access gaps, rather than pretending that every citation received a complete reading.

## Reading depth

- **F** means full text was accessible and relevant passages were inspected. It does **not** mean every proof, appendix, or line was checked.
- **A** means a primary abstract or author, publisher, or institutional publication page was inspected. Conclusions stay within that abstract.
- **D** means official implementation documentation was inspected. Documentation is evidence of a feature, not an independently verified theorem or benchmark.
- **S** means an indexed primary abstract or publication record was screened, but opening the primary source failed. This identifies an audit requirement, not a settled technical comparison.
- **M** means metadata or an existing local reference only. No technical conclusion depends solely on these entries.
- **T** means author slides were inspected; the corresponding full paper was not obtained.

Each entry separates the reported result from its consequence for Minyar. The latter is the review's inference. Performance numbers from papers are not reproduced as predictions for Minyar.

## Reference counting and scheduling

### R01 Baker 1978

[List Processing in Real Time on a Serial Computer](https://www.plover.com/misc/hbaker-archive/RealTimeGC.html). **F**, author archive; relevant incremental reclamation discussion.

Early work already discusses incremental memory management and reference-count destruction work. Consequently, breaking recursive destruction into bounded steps is historical prior art. The modern language, representation, and compiler contract must supply any stronger contribution.

### R02 Ritzau and Fritzson 2002

[Decreasing Memory Overhead in Hard Real-Time Garbage Collection](https://www.diva-portal.org/smash/get/diva2:743471/fulltext01.pdf), EMSOFT 2002. **F**, representation and allocator-driven service sections.

RTRC segments objects into equal-sized blocks and performs lazy reclamation related to allocation work. The prototype has qualifications, including array handling. This is a close precursor for allocator and representation arguments; precleaning capacity alone is insufficient novelty.

### R03 Boehm 2004

[The Space Cost of Lazy Reference Counting author slides](https://www.hboehm.info/popl04/refcnt.pdf), accompanying POPL 2004 paper. **T**; [paper metadata](https://research.google/pubs/the-space-cost-of-lazy-reference-counting/).

The slides exhibit space amplification with variable-sized objects under lookahead-free lazy RC and bounded deallocations per operation sequence. They identify assumptions that matter for a claimed space theorem. Exact lower-bound constants and their full scope require the paper.

### R04 Lam and Parreaux 2024

[Being Lazy When It Counts: Practical Constant-Time Memory Management for Functional Programming](https://lptk.github.io/files/ctrc-2024-05-09.pdf), FLOPS 2024. **F**, algorithm, allocation effects, evaluation, and relevant appendix lemmas.

CTRC already combines deferred RC, segmented cells, a restricted constant-time interface, and Koka reuse optimizations. Its formal accounting distinguishes delayed references from eager counts. This is the closest baseline for Minyar's bounded reclamation and reuse proposals.

### R05 Bacon Cheng and Rajan 2003

[A Real-Time Garbage Collector with Low Overhead and Consistent Utilization](https://research.ibm.com/publications/a-real-time-garbage-collector-with-low-overhead-and-consistent-utilization--1), Metronome. **A**.

The primary abstract describes fully incremental collection and predictable utilization. A language-level cleanup proposal must distinguish its guarantee from established real-time collector scheduling, rather than treating short collection slices as new.

### R06 Robertz and Henriksson 2003

[Time-Triggered Garbage Collection: Robust and Adaptive Real-Time GC Scheduling for Embedded Systems](https://fileadmin.cs.lth.se/cs/Personal/Sven_Gestegard_Robertz/publ/LCTES03-robertz.pdf), LCTES. **F**, abstract and scheduling rationale.

Time-triggered collector service and adapting work to collection deadlines are established. Minyar's possible contribution lies in compiler-derived workload obligations and their composition with actual service, rather than merely polling between events.

### R07 Auerbach and colleagues 2008

[Tax-and-spend: Democratic Scheduling for Real-Time Garbage Collection](https://research.ibm.com/publications/tax-and-spend-democratic-scheduling-for-real-time-garbage-collection). **A**.

Collection scheduling already balances mutator activity and memory consumption. Budget taxation and spending are not novel by themselves. The relevant comparison is whether Minyar derives stronger compositional facts under comparable mutator assumptions.

### R08 Le Boudec and Thiran 2001

[Network Calculus](https://leboudec.github.io/netcal/latex/netCalBook.pdf), LNCS 2050; maintained online edition dated August 2022. **F**, arrival/service definitions and backlog theorem 1.4.1.

Arrival and service curves imply deterministic backlog bounds. This supplies existing mathematical machinery for a potential cleanup model. The difficult new step would be deriving sound reclamation arrivals and memory consequences for a shared heap.

### R09 TLSF implementation

[mattconte/tlsf](https://github.com/mattconte/tlsf). **D**, implementation documentation.

Constant-time allocator algorithms already exist. Allocation metadata complexity does not make page faults, copying during resize, arbitrary backing frees, or operating-system scheduling constant-time. A Minyar hardware deadline would need explicit additional assumptions.

## Ownership borrowing and reuse

### R10 Ullrich and de Moura 2019

[Counting Immutable Beans: Reference Counting Optimized for Purely Functional Programming](https://arxiv.org/abs/1908.05647). **A**, preprint.

Borrow inference and reuse of unshared allocations are already established techniques. A Minyar contribution must account for its mutable aliases and deferred ownership, or demonstrate a distinctly stronger inference or resource result.

### R11 Reinking Xie de Moura and Leijen 2021

[Perceus: Garbage Free Reference Counting with Reuse](https://www.microsoft.com/en-us/research/uploads/prod/2021/06/perceus-pldi21.pdf), PLDI. **F**, introduction and ownership/reuse discussion.

Perceus formalizes precise RC and reuse for a functional core with explicit control flow. Garbage freedom and in-place reuse are major existing results. Minyar should compare delayed retained storage and effects on shared mutation explicitly.

### R12 Lorenzen and Leijen 2022

[Reference Counting with Frame Limited Reuse](https://www.microsoft.com/en-us/research/publication/reference-counting-with-frame-limited-reuse/), ICFP. **A**; full PDF fetch failed.

Reuse guided by limited frames is already a research topic. This must be investigated further before claiming a new stack/frame-based reuse rule. The present review does not infer details of its proofs from the title.

### R13 Lorenzen Leijen and Swierstra 2023

[FP²: Fully In-Place Functional Programming](https://webspace.science.uu.nl/~swier004/publications/2023-icfp.pdf), ICFP. **F**, FIP discipline and conditional reuse.

FIP gives allocation and stack guarantees under ownership conditions. Allocation-free execution is not constant execution time. This provides a stringent baseline for any restricted Minyar path intended to avoid memory-management work.

### R14 Proust 2017

[ASAP: As Static As Possible Memory Management](https://www.cl.cam.ac.uk/techreports/UCAM-CL-TR-908.pdf), Cambridge technical report 908, based on doctoral work. **F**, abstract and design passages.

Static automatic memory management with mutation and polymorphism is established research. Inference without manual lifetime annotations cannot alone identify novelty. Precision, compilation cost, and remaining runtime obligations are the useful dimensions.

### R15 Brandon and colleagues 2026

[Fully-Automatic Type Inference for Borrows with Lifetimes](https://www.cs.princeton.edu/~mpmilano/publication/fully-automatic-type-inference/), PACMPL OOPSLA1, April 2026. **A**; linked ACM PDF inaccessible.

Morphic infers borrows with lifetimes and inserts RC where typing otherwise fails, in a pure functional setting. The abstract reports substantial eliminated RC operations. This directly disqualifies a broad claim of being first to obtain borrowing performance without annotations.

### R16 Lobster documentation

[Memory management](https://aardappel.github.io/lobster/memory_management.html). **D**.

Lobster documents inferred ownership and borrowing with RC fallback. This is an additional implementation baseline for annotation burden. Its documented mechanisms must not be treated as a proof about arbitrary Minyar mutation.

### R17 Racordon and colleagues 2022

[Mutable Value Semantics](https://research.google/pubs/mutable-value-semantics/). **A**.

Mutable value semantics is an alternative way to simplify ownership and optimization. Adopting it would change Minyar's observable shared mutation. Comparisons must not obtain an apparent advantage by silently removing that behavior.

### R18 Lorenzen Leijen Swierstra and Lindley 2025

[First-Order Laziness](https://www.microsoft.com/en-us/research/wp-content/uploads/2025/09/first-order-laziness-icfp2025.pdf), ICFP. **F**, lazy-object reuse discussion.

Laziness and reuse can coexist under explicit conditions. Lazy computation differs from delayed reclamation, but this work broadens the reuse audit and prevents an unsupported claim that any reuse amid deferral is unprecedented.

## Resource analysis

### R19 Hoffmann and Jost 2022

[Two Decades of Automatic Amortized Resource Analysis](https://www.cs.cmu.edu/~janh/assets/pdf/HoffmannJ21.pdf), MSCS publication 2022; author manuscript filename predates publication. **F**, survey overview and relevant resource-analysis discussion.

Potential-based type systems have long inferred resource bounds. Adding numeric effects or linear credits is not a sufficient contribution. Minyar would need a new treatment of delayed heap obligations, a stronger inference result, or preservation through its implementation.

### R20 Niu and Hoffmann 2018

[Automatic Space Bound Analysis for Functional Programs with Garbage Collection](https://www.cs.cmu.edu/~janh/assets/pdf/NiuH18.pdf), LPAR. **F**, cost semantics, sharing treatment, and introduction.

The analysis bounds heap high-water usage with an immediate ideal collector and supports sharing through a sound comparison semantics. This demonstrates that static space analysis is established, while leaving a concrete comparison to Minyar's deferred collector and allocator.

### R21 Albert Genaim and Gómez Zamalloa 2013

[Heap Space Analysis for Garbage Collected Languages](https://www.sciencedirect.com/science/article/pii/S0167642312001931). **S**; indexed publisher abstract screened, primary fetch returned 403.

The screened abstract describes collector/lifetime-sensitive heap analysis. It is a serious priority-check requirement for direction 1. The review does not claim that collector-parametric space analysis is new or that this work lacks a particular feature.

### R22 Lian and Wang 2025

[Automatic Linear Resource Bound Analysis for Rust via Prophecy Potentials](https://arxiv.org/abs/2502.19810). **A**, preprint.

The abstract describes linear resource bounds with shared and mutable borrows. Ownership-aware resource analysis is therefore a close topic, rather than an empty area. General-purpose shared RC and scheduler obligations require a separate comparison.

### R23 Lorenzen 2026

[Persistent Amortised Analysis, Operationally](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.ICALP.2026.185), ICALP. **A**.

Operational amortized analysis of persistent lazy computations is current work. Potential credits must cope with persistence rather than being duplicated freely through aliases. This is relevant proof machinery, without identifying lazy evaluation with dead-heap cleanup.

## Reachability acyclicity and capabilities

### R24 Lu and Potter 2004

[On Reachability and Acyclicity](https://cgi.cse.unsw.edu.au/~reports/papers/0434.pdf), UNSW technical report 0434. **F**, type/region discipline and reachability motivation.

Region-parametric typing already relates reachability and acyclicity. Its organization permits distinctions between inter-region and internal edges. A type-based cycle restriction is old; Minyar would need more precise inferred mutation permissions or a stronger operational guarantee.

### R25 Joisha 2006

[Compiler Optimizations for Nondeferred Reference-Counting Garbage Collection](https://doi.org/10.1145/1133956.1133976), ISMM. **M**, metadata and existing Minyar related-work notes; attempted full-text mirror failed.

This is an outstanding comparison for compiler RC optimization and type connectivity. No new technical finding is attributed to it here. Inspect the complete paper before a submission claims priority for type-graph or stack optimizations.

### R26 Zanardini and Genaim 2013

[Inference of Field-Sensitive Reachability and Cyclicity](https://arxiv.org/abs/1306.6526), preprint with later revision. **A**.

Field-sensitive reachability and cyclicity inference predates Minyar. The proposed mutation analysis must demonstrate precision or complexity beyond an ordinary adaptation of such analyses, while preserving sharing and mutation semantics.

### R27 Wei and colleagues 2023

[Polymorphic Reachability Types: Tracking Freshness, Aliasing, and Separation in Higher-Order Generic Programs](https://arxiv.org/abs/2307.13844), preprint associated with POPL 2024 work. **A**.

Freshness, aliasing, separation, and polymorphism already have a reachability-type treatment. Allocation freshness alone is insufficient for acyclic insertion if the new object contains a reference back to the receiver.

### R28 Jia Wei He Bao and Rompf 2024 to 2026

[Escape with Your Self: Sound and Expressive Bidirectional Typing with Avoidance for Reachability Types](https://arxiv.org/html/2404.08217v6), v6 dated 10 June 2026. **F**, inference and soundness overview/conclusion.

Bidirectional reachability typing with avoidance is current, mechanized work. A proposed Minyar inference system must identify a distinct guarantee and compare its expressiveness, rather than assume reachability annotation inference is missing.

### R29 Deng He Jia Bao and Rompf 2025 to 2026

[Capture Now, Consume Later: Reachability Types with Flow-Sensitive Effects for Higher-Order Ownership Transfer](https://arxiv.org/abs/2510.08939), v2 dated 26 September 2026. **A**, preprint; full text inaccessible.

Flow-sensitive effects and ownership transfer are already being combined with reachability types. Older searches may find the earlier title, Free to Move. This recent version is a mandatory follow-up before claiming a novel uniqueness or alias invalidation scheme.

### R30 Scala separation checking

[Separation checking](https://docs.scala-lang.org/scala3/reference/experimental/capture-checking/separation-checking.html). **D**, experimental language documentation.

Capture checking has documented separation/freshness mechanisms. An annotation burden comparison should include existing capability designs. Experimental documentation does not establish performance, nor remove the need to prove Minyar's owning-heap invariant.

### R31 Pham and colleagues 2026

[Classifying Capabilities Extended Version](https://arxiv.org/abs/2607.24504), July 2026 preprint. **A**.

The abstract describes hierarchical capability classifiers, exclusion guarantees, mechanization, and implementation in Scala. Capability classification is a populated research area. Applying capabilities to asynchronous cleanup must provide additional resource semantics.

### R32 Mode Crossing 2026

[Mode Crossing](https://people.mpi-sws.org/~bpeters/papers/mode-crossing.pdf), ICFP 2026. **F**, introduction and mode/type discussion.

Type information can strengthen mode properties and reduce annotation burdens. This is relevant to any whole-language inference proposal. A convenient combination of locality and uniqueness modes is insufficient novelty by itself.

### R33 OxCaml modes

[Modes introduction](https://oxcaml.org/documentation/modes/intro/). **D**.

Official documentation describes several orthogonal modes covering properties such as locality and uniqueness. The baseline for an ergonomic systems language includes these combinations, rather than only conventional explicit Rust lifetimes.

### R34 Yanovski Dang Jung and Dreyer 2021

[GhostCell: Separating Permissions from Data in Rust](https://plv.mpi-sws.org/rustbelt/ghostcell/paper.pdf), ICFP. **M**, record screened; paper and alternate mirror fetches failed.

Inspect this permission/data separation work before claiming a new capability discipline for shared mutable structures. The present report does not attribute a detailed theorem to an inaccessible paper.

## Regions layouts concurrency and cycles

### R35 Arvidsson and colleagues 2023

[Reference Capabilities for Flexible Memory Management](https://arxiv.org/abs/2309.02983), OOPSLA 2023 work. **A**.

The abstract describes isolated regions with varying local memory strategies and capability-controlled access. Region-local reclamation and capability-based isolation are existing foundations. A Minyar direction must add a new bound or automated selection rule.

### R36 Clebsch and colleagues 2017

[Orca: GC and Type System Co-Design for Actor Languages](https://www.ponylang.io/media/papers/orca_gc_and_type_system_co-design_for_actor_languages.pdf), OOPSLA. **F**, abstract and type/collector rationale.

ORCA co-designs actor capabilities and collection, including zero-copy transfers and avoiding global stop-the-world behavior. This does not imply an arbitrary actor action has bounded latency. Actor isolation alone would repeat existing work.

### R37 Jung Kim Parkinson and Kang 2024

[Concurrent Immediate Reference Counting](https://www.microsoft.com/en-us/research/publication/concurrent-immediate-reference-counting/), PLDI. **A**.

CIRC separates reference-count work from deferred reclamation and addresses retention consequences of delayed decrements. It is relevant to the reuse/retention tradeoff. A concurrent throughput result must not be confused with Minyar's single-mutator work cap.

### R38 Lahaie Bertrand and colleagues 2025

[Arborescent Garbage Collection: A Dynamic Graph Approach to Immediate Cycle Collection](https://oestoleary.com/papers/ISMM25.pdf), ISMM. **F**, graph maintenance and reconnecting discussion.

Dynamic graph techniques can identify cycles for immediate reclamation. Reconnecting graph structures can involve large traversals. This prevents equating immediate cycle collection with constant-time or interruption-safe collection.

### R39 Vollmer and colleagues 2019

[LoCal: A Language for Programs Operating on Serialized Data](https://kar.kent.ac.uk/95505/), PLDI. **S**, indexed institutional abstract screened; record/PDF access failed.

Serialized recursive representations already have language and compiler support. Treat this as a required detailed audit for layout work, rather than infer the limits of its operational semantics from a search result.

### R40 Singhal and colleagues 2024

[Optimizing Layout of Recursive Datatypes with Marmoset](https://arxiv.org/pdf/2405.17590), ECOOP; extended version. **F**, introduction and hard/soft layout constraints.

Marmoset chooses recursive datatype layouts using access analysis and a constraint cost model. Automatic layout selection is established. Minyar would need an additional constraint, guarantee, or algorithm that changes the problem materially.

### R41 Singhal and colleagues 2026

[SoCal: A Language for Memory-Layout Factorization of Recursive Datatypes](https://arxiv.org/pdf/2605.01140), May 2026 preprint. **F**, layout, sharing, and implementation passages.

SoCal factors recursive representations across buffers, including indirections for sharing and relevant mutation benchmarks. It cannot be dismissed as only handling unshared trees. A reclamation-aware mutable layout result needs a direct, detailed comparison.

### R42 Rainey and colleagues 2026

[LoCalMem: Type-Directed Adaptive Serialization for Location- and Content-Addressable Memory](https://kar.kent.ac.uk/116036/), PACMPL ICFP. **A**, deposited August 2026; linked full PDF fetch failed.

The abstract formalizes boundaries between sharing and serialization, with bounds on boundary separation and update work. It assumes pure functional values. A layout proposal must distinguish cleanup bounds and observable mutable identity from these existing boundary/cost results.

## Reactive programs and compilation

### R43 Krishnaswami Benton and Hoffmann 2012

[Higher-Order Functional Reactive Programming in Bounded Space](https://www.cs.cmu.edu/~janh/papers/bounded_frp.pdf), POPL. **F**, abstract and introduction.

The language statically bounds reactive dataflow graph size while supporting higher-order streams. Bounded-space reactive language design is therefore established. Minyar's shared heap and deferred cleanup obligations require a distinct comparison.

### R44 Bahr Graulund and Møgelberg 2019

[Simply RaTT: A Fitch-Style Modal Calculus for Reactive Programming without Space Leaks](https://arxiv.org/abs/1903.05879), ICFP work. **A**.

Modal reactive typing excludes implicit leaks while maintaining causality and productivity. Leak prevention should not be treated as a numeric bound on arbitrary application storage or collector backlog.

### R45 Yokoyama Moriguchi and Watanabe 2021

[A Functional Reactive Programming Language for Small-Scale Embedded Systems with Recursive Data Types](https://www.jstage.jst.go.jp/article/ipsjjip/29/0/29_685/_article/), JIP. **A**.

EmfrpBCT uses sized recursive datatypes for static memory requirements and termination. A meaningful Minyar contribution should preserve substantially useful expressiveness while proving its own resource result, rather than merely restrict recursion.

### R46 Bahr 2025 to 2026

[Simple Modal Types for Functional Reactive Programming](https://arxiv.org/abs/2512.09412), preprint, revised August 2026. **A**.

This recent work simplifies modal reactive restrictions and addresses space/time leaks in asynchronous programs. It is another active neighbor of the event-contract proposal. The abstract does not establish Minyar's proposed numeric cleanup guarantees.

### R47 Lopes Lee Hur Liu and Regehr 2021

[Alive2: Bounded Translation Validation for LLVM](https://users.cs.utah.edu/~regehr/alive2-pldi21.pdf), PLDI. **F**, introduction and limits of bounded validation.

Alive2 validates semantic refinement within a bounded setting. It is useful supporting machinery, but ordinary semantic validation does not establish preservation of heap retention, cleanup service, or cost guarantees.

### R48 CerCo project 2010 to 2013

[Certified Complexity project description](https://cordis.europa.eu/project/id/243881). **A**, official funded project description; dates are project dates.

The description proposes a verified compiler preserving concrete complexity from C to microcontroller code and returning cost annotations. It establishes prior research aims, not proof that every described result was delivered. Detailed results need their own paper audit.

### R49 Muller and Hoffmann 2019

[Combining Source and Target Level Cost Analyses for OCaml Programs](https://www.cs.cmu.edu/~janh/assets/pdf/MullerH19.pdf). **F**, introduction and source/target analysis design.

This work combines symbolic source analysis with costs from lower-level execution. A source-to-runtime cost link is not novel by itself. Delayed shared ownership and optimization-sensitive cleanup would be the more specific target.

### R50 Shyamsunder 2026

[Formal Performance and Compile Time Guarantees for Compiler Optimization Heuristics](https://arxiv.org/abs/2608.20137), August preprint, three-page FMCAD Student Forum submission. **A**.

The abstract studies mechanized cost and convergence guarantees for optimization heuristics. It is preliminary research, not evidence of a production compiler solving Minyar's proposed problem. It nevertheless weakens a broad first-cost-preserving-optimizer claim.

### R51 Mokhov Mitchell and Peyton Jones 2018

[Build Systems à la Carte](https://www.microsoft.com/en-us/research/wp-content/uploads/2018/03/build-systems-final.pdf), ICFP. **F**, introduction and task/rebuilder distinctions.

Incremental dependency management has a formal landscape of existing designs. Module hashing and early cutoff are insufficient novelty. Minyar would need a useful ownership/resource-analysis incrementality theorem or demonstrably new algorithm.

## Follow up before claiming priority

Obtain full texts for R03, R12, R15, R21, R25, R29, R34, R39, and R42, then inspect their closest technical sections and artifacts. These gaps particularly affect the reuse, reachability, and collector-sensitive space hypotheses. Extend citation chaining to older region inference, shape analysis, escape analysis, WCET, real-time Java, and incremental static analysis before a formal submission. No absence claim in this review substitutes for that step.

The report intentionally makes no claim to exhaust all programming-language novelty. Its coverage is strongest around the constraints and existing mechanisms that make Minyar distinctive enough to motivate a research program.
