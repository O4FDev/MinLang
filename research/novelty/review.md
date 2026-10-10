# Minyar research novelty assessment

Review date: 3 October 2026. Scope: the whole language, starting with memory management. Audience: Minyar's author deciding which substantial research problem to pursue. This assessment combines primary literature with the current repository and its retained research assessments. It proposes research targets; it does not establish that Minyar has already achieved them.

## Main finding

**Minyar has credible routes to a substantial research contribution, but its current bounded reference-counting mechanism is not, by itself, a defensible novelty claim.** Incremental destruction, automatic ownership inference, allocation reuse, capability-controlled mutation, and optimized recursive layouts all have substantial prior art.

The strongest direction I found is a compiler and runtime contract that connects **the work a source operation creates, the cleanup service it receives, and the memory it continues to retain**. This would extend Minyar's existing accounting into a useful guarantee for ongoing event-driven programs. It is a research hypothesis, rather than an established gap: collector-sensitive space analysis and real-time scheduling are particularly important comparisons.

I would pursue these three directions in this order:

| Priority | Proposed contribution | Why it fits Minyar | What would make it substantial |
| --- | --- | --- | --- |
| 1 | Compositional cleanup and retained-memory contracts | Builds on explicit ownership, queued work, and event experiments | A proved source-to-runtime guarantee connecting mandatory work, deferred debt, actual service, and physical capacity |
| 2 | Reuse that remains effective when cleanup is delayed | Addresses a potential cost of the existing deferral policy | A safe, inexpensive way to exploit proven absence of observable aliases without draining unrelated garbage |
| 3 | More permissive inferred mutation while preserving an acyclic owning heap | Removes a concrete restriction in the language | A precise, modular analysis that admits useful currently rejected mutations with a controlled inference cost |

These can become related papers or stages of one thesis. Attempting all of them simultaneously would make it difficult to identify what caused an improvement. The first is the best main project; the second is a high-risk optimization hypothesis; the third is the strongest independent language-design project.

Other plausible directions concern reclamation-aware layouts, checked cost-preserving compilation, and predictable incremental inference. They require larger compiler changes or a deeper prior-art audit. Concurrency and unrestricted cycles would greatly expand the problem and are poor first extensions for this research agenda.

## Evidence and scope

The [source register](sources.md) records 51 research and implementation sources, including older foundations and work published or revised in 2026. Relevant sections of 22 full texts were inspected, alongside 20 primary abstracts/publication pages, four official implementation documents, and one author slide deck. Four additional records were screened with access limitations. Each entry states its reading depth. This is a broad, targeted literature review, not a claim to have checked every proof in 51 papers or exhausted every citation chain.

The search concentrated on reference counting and real-time scheduling; static space and cost analysis; ownership, borrowing, reachability and modes; regions and recursive representations; reactive programming; and compiler validation and incrementality. The [method and repository snapshot](method.md) records search families, limitations, and the local evidence used. Statements about published systems are sourced. Candidate mechanisms, rankings, and experiment designs below are this review's proposals.

The repository base commit was `c2c9eff1343ad80d78ad5a32801fb135a530f3fb`. The reviewed working tree contains extensive changes beyond that commit. The [snapshot manifest](snapshot.json) hashes the selected local files; this review applies to those contents, rather than assuming that the base commit alone contains them. Existing experiment results are reported from their assessments, not independently rerun for this literature review.

The report asks whether a result could be new under a clear set of assumptions. It does not infer novelty from the absence of an exact phrase in search results. A published precursor may have the same theorem under different terminology, and an inaccessible paper remains an unresolved comparison.

## What Minyar currently provides

Minyar is a statically typed language compiling to native code through LLVM, with a self-hosted compiler and a C bootstrap. Its managed records, Lists, and Bytes can have observable shared mutation: aliases see updates. That behavior is part of the comparison problem. Replacing it with immutable values, implicit copying, or pervasive exclusive ownership would require an explicit language change. See the [language reference](../../docs/language.md) and [architecture](../../docs/architecture.md).

The owning heap is intended to remain acyclic. Recursive shapes and shared DAGs can be constructed, but potentially cycle-forming List insertions and reference-field writes are restricted using declared type reachability. This is deliberately conservative: some safe writes of freshly constructed values are rejected because their types can reach the receiver type. Constructors have a separate safety rationale because the newly allocated receiver cannot be accessed before construction finishes.

The compiler tracks owned producer results, transfers, borrows, and temporary ownership. It protects expression temporaries where later evaluation could invalidate an earlier reference. This provides useful material for an ownership IR, but it is not yet a general inferred reachability or lifetime system.

The default memory profile uses a system allocator and incremental, single-threaded, non-atomic RC. Fixed and lazy pools and eager alternatives also exist. The runtime accounts for object fields, detached local owners, temporary owners, and task completion. The public bounded contract has several critical qualifications:

- K caps a cleanup batch at a runtime service point. It does not cap an entire source statement, function, or event. Some operations can contain multiple batches.
- Synchronous visits to stack owners remain necessary before their storage expires. Work cannot safely be deferred by leaving a queued pointer into an expired stack frame.
- Fair progress for an active old task is not a uniform waiting-time or retained-space theorem for every object.
- Object traversal accounting excludes other potentially large costs, including initialization, buffer copies, collection growth, allocation, backing frees, page faults, I/O, and operating-system delays.

These distinctions are documented in the [bounded runtime contract](../../docs/bounded-runtime-contract.md) and [memory policy](../../docs/runtime-memory.md). They constrain any stronger language guarantee.

The current research is useful but does not establish a general advantage. The [follow-up assessment](../reclamation/followup-assessment.md) records a corrected K1 Text-view counterexample and actual-runtime fairness experiments. It also records cases where FIFO or eager reclamation performs better: at K8 the current scheduler retained more dead managed bytes in the selected workload, and at the fastest tested steady arrivals its K32 response tails lost to those baselines. The quiet-window experiment began with little residual debt, so it is weak evidence about recovery under substantial backlog.

The [prospective acceptance suite](../reclamation/acceptance.md) already specifies shared event allowances, nested scope composition, interruptible idle work, and finite recovery. Its integration adapter is intentionally incomplete. Implementing those interfaces would improve the language and testability, but that work alone would not establish a new research result. A stronger theorem, inference method, or measured tradeoff is needed.

The compiler's measured self-compilation budgets and bounded lexical optimization lookahead are valuable engineering properties. They are not currently an asymptotic theorem about compilation complexity. Its ordinary frontend still interleaves parsing, checking, ownership decisions, and LLVM emission in a shared source unit. Several ambitious directions below would benefit from an explicit typed intermediate representation before their algorithms are added.

## Claims that the literature already occupies

The table identifies broad claims that should be avoided. It does not say that Minyar's exact implementation duplicates a particular paper.

| Broad proposed claim | Closest prior evidence | Consequence for a Minyar claim |
| --- | --- | --- |
| RC destruction can be processed incrementally | Baker, RTRC, CTRC, R01–R04 | Bounded batches alone are insufficient |
| Constant-time automatic memory management for an appropriate restricted interface | CTRC, R04 | Specify a stronger guarantee or materially different useful assumptions |
| Collector work can be budgeted or scheduled around mutator demand | Metronome, time-triggered GC, Tax-and-spend, R05–R07 | Event scopes and idle polling need a new analysis or composition result |
| Ownership and borrowing can be inferred without explicit lifetimes | ASAP, Morphic, Lobster, R14–R16 | Annotation-free borrowing is already occupied |
| Functional-looking code can reuse allocations in place | Beans, Perceus, frame-limited reuse, FIP, R10–R13 | Reuse requires a distinct delayed/shared-ownership result |
| Types or analyses can reason about heap reachability and cycles | Lu/Potter, field-sensitive analysis, reachability types, R24–R29 | A type-graph restriction is not new enough |
| Types can infer resource or heap-space bounds | AARA, GC-space analysis, Rust potentials, R19–R23 | The new part must concern an additional cost semantics or useful inference result |
| Locality and uniqueness can be language modes | OxCaml and Mode Crossing, R32–R33 | Combining familiar modes is insufficient |
| A compiler can choose recursive layouts automatically | LoCal, Marmoset, SoCal, LoCalMem, R39–R42 | Add a distinct reclamation/mutation constraint and result |
| Reactive language restrictions can prevent space leaks or bound storage | Bounded FRP, RaTT, EmfrpBCT, R43–R46 | Numeric bounds for the actual delayed heap need a separate argument |
| Regions or actors can permit local memory strategies | Reference Capabilities, ORCA, R35–R36 | Actor-local collection is insufficient |
| Compiler reasoning can connect source costs to lower-level costs | CerCo and source/target cost analysis, R48–R49 | Cost-aware lowering is not an empty field |
| Incremental builds can reuse unchanged dependencies | Build Systems à la Carte, R51 | Hashing bodies and interfaces is not a research contribution alone |

### The closest memory baseline

CTRC already combines deferred RC, segmented representations, an allocation-sensitive interface, and reuse. Its count relations explicitly accommodate references retained by deferred work. It therefore blocks both a broad constant-time-RC claim and a broad claim that nobody has recognized the distinction between an eager ownership count and a physical delayed count. [CTRC](https://lptk.github.io/files/ctrc-2024-05-09.pdf)

Boehm's variable-size examples show why object counts cannot stand in for bytes or reusable capacity. The inspected slides concern lookahead-free implementations with bounded deallocations per operation sequence; they are not an impossibility theorem for every statically informed collector. A proposal must state how its extra information or assumptions change that problem. [Boehm's slides](https://www.hboehm.info/popl04/refcnt.pdf)

RTRC is relevant because segmented allocation and allocation-related cleaning are older than CTRC. A reserved supply of cleaned storage should be treated as an established building block. [RTRC](https://www.diva-portal.org/smash/get/diva2:743471/fulltext01.pdf)

### Recent work changes the language shortlist

Morphic's April 2026 paper describes fully automatic borrow inference with RC insertion as a fallback in a pure functional language. The broad aim of obtaining borrowing performance without lifetime annotations is therefore an existing result. Whether its full machinery supplies anything like Minyar's proposed delayed cleanup contracts remains an audit question; the abstract cannot settle that. [Morphic](https://www.cs.princeton.edu/~mpmilano/publication/fully-automatic-type-inference/)

Reachability inference is also active. The June 2026 version of Escape with Your Self and the September 2026 revision of Capture Now, Consume Later are particularly close to inferred freshness, avoidance, and ownership transfer. These are essential comparisons for directions 2 and 3, not peripheral citations. [Escape with Your Self](https://arxiv.org/html/2404.08217v6), [Capture Now, Consume Later](https://arxiv.org/abs/2510.08939)

SoCal already includes sharing through indirection, and LoCalMem formalizes boundaries between sharing and serialization with update-cost results. An automatic layout proposal cannot dismiss this family as only dealing with unshared trees. LoCalMem's stated pure-value setting is a meaningful distinction from Minyar's observable mutable aliases, but that distinction alone is not a contribution. [SoCal](https://arxiv.org/pdf/2605.01140), [LoCalMem](https://kar.kent.ac.uk/116036/)

## Direction 1 Compositional cleanup and retained memory

### Proposed research claim

For a useful accepted subset of Minyar, infer or check source-level contracts describing mandatory synchronous owner work, generated deferred reclamation obligations, allocation demand, and retained capacity. Compose those contracts across calls and event boundaries. Prove that a declared service policy suffices for a bound on residual obligations and physical managed storage, while each sensitive action respects its declared management allowance.

The claim must say which loops, sizes, native calls, and recursion require supplied bounds. It need not infer a finite answer for every program. Returning an unknown bound or rejecting a critical-path contract is a sound and practical outcome.

This would be substantially more useful than a per-call K cap: an application author could reason about an entire callback, repeated callbacks, and memory needed between cleanup opportunities. The proposed novelty is the treatment of delayed shared ownership and its connection to the actual compiler/runtime, not the existence of numeric effects.

### The closest prior art and the remaining question

AARA supplies potential-based bound inference; existing GC-space analysis handles sharing under an ideal collection semantics. The screened Albert/Genaim/Gómez Zamalloa paper is a warning that collector-sensitive heap analysis also exists. Real-time collectors and reactive type systems already address portions of scheduling and storage. [AARA survey](https://www.cs.cmu.edu/~janh/assets/pdf/HoffmannJ21.pdf), [GC-space analysis](https://www.cs.cmu.edu/~janh/assets/pdf/NiuH18.pdf), [collector-sensitive analysis record](https://www.sciencedirect.com/science/article/pii/S0167642312001931), [bounded FRP](https://www.cs.cmu.edu/~janh/papers/bounded_frp.pdf)

**Unresolved novelty question:** can Minyar provide a useful, compositional bound for the combination of deferred owning edges, suspended owner frames, observable sharing/mutation, variable-sized storage, and event-level service, with a sound connection to emitted code? This review found the combination worth investigating; it did not establish that no earlier system covers it.

The following comparisons define the hypothesis more precisely. A narrower focus in a paper does not prove its technique cannot be extended; this table identifies what must be demonstrated in the proposed result.

| Comparison | Relevant established property | Additional obligation proposed for Minyar |
| --- | --- | --- |
| Current Minyar | Local batches account for deferred visits; mandatory stack exits remain separate | Compose a whole-action bound and relate generated obligations to physical capacity |
| CTRC | A constant-time interface under its representation and effect assumptions | Account for Minyar's action boundaries and full owner-storage obligations under clearly comparable assumptions |
| GC-space analysis | Static heap bounds with sharing under its stated collector semantics | Bound storage retained by the actual delayed runtime, including pending owners and backing capacity |
| Real-time collector scheduling | Service can be coordinated with mutator demand | Derive sound demand summaries from source operations and preserve them through lowering |
| Bounded reactive languages | Their disciplines control reactive storage or leak behavior | Integrate the mutable owning heap and actual deferred-service protocol into the accepted fragment |
| Collector-sensitive heap analysis | An indexed abstract indicates relevant prior work | Full-text audit required; no claimed missing property established here |

One useful separation would be a theorem about an abstract ownership machine, a theorem connecting its contracts to Minyar's runtime, and experiments establishing how restrictive or expensive the accepted fragment is. Joining known techniques can be a contribution if the interaction requires a new argument and yields a useful guarantee; a feature-combination table alone cannot establish that.

### The accounting problem

A contract needs more than a queue length. Consider releasing the last live root of a chain whose final node owns a large Bytes buffer. Initially one task may be queued. The later cleanup can expose thousands of nodes and retain the large buffer until its ancestors are processed. A bound based only on the initial queue hides almost all future work and retained storage.

Similarly, one queued List with many owning elements has a different cleanup obligation from one scalar record. A dead small wrapper may retain a large backing allocation. Pool free bytes may be insufficient for an allocation in a particular size class. Live Text views can legitimately keep an entire backing allocation live, so that storage must not be falsely classified as dead collector debt.

The proposed analysis should track a resource vector rather than one counter:

| Quantity | Meaning | Why it cannot be replaced by another column |
| --- | --- | --- |
| Mandatory work | Owner visits and immediate actions that must finish synchronously | An event's queued-work allowance does not cover them |
| Remaining cleanup work | All future visits/completions attributable to released ownership | Unexposed descendants can dwarf visible tasks |
| Physical retained storage | Managed objects, backing capacity, and owner metadata still allocated | Equal work does not imply equal bytes |
| Allocation demand | Size-class demands and resize/copy requirements | Total free bytes do not establish allocatability |
| Service obligation | Minimum actual cleanup supplied over relevant intervals | An upper work cap alone gives no progress guarantee |

An operational semantics can distinguish logical reachability, physical counts, and pending cleanup edges. Compiler summaries can use conservative potential charged during construction/growth, ownership-aware shape bounds, or explicit annotations for difficult structures. Aliases must not duplicate spendable credit. A general shared heap makes that issue central rather than incidental.

The runtime should not scan a released graph merely to compute its contract. That would move the same large pause into the accounting path. A successful method would maintain sufficient information incrementally or derive it statically, and include the maintenance cost in the bound.

### Relating generated work to guaranteed service

A possible mathematical component is an arrival envelope `alpha` for offered cleanup work and a service curve `beta` for completed cleanup. Both must cover the same units. Existing network calculus gives the schema:

```text
remaining_work(t) <= initial_debt + sup over u >= 0 of max(0, alpha(u) - beta(u))
```

Initial debt can instead be included in the arrival model. A burst/rate arrival model and a rate/lag service model can yield a finite bound when service capacity meets demand. This is established queueing mathematics, not a proposed new theorem. [Network Calculus theorem 1.4.1](https://leboudec.github.io/netcal/latex/netCalBook.pdf)

The research lies in making the inputs sound. An arrival model must account for cascaded future cleanup, including work not yet visible in a queue. A service model must describe actual work supplied while backlogged, not how much a poll is allowed to do. Compiler and scheduler composition must preserve those facts. A waiting-time theorem for an individual task would require an additional ordering argument; a global backlog result alone does not provide it.

A work bound still needs a separate connection to bytes and allocatable capacity. This may require size-class potentials or direct storage summaries. Multiplying work by a universal maximum object size might be sound for a restricted pool but so loose that it is useless. Finding tighter sound bounds without expensive runtime graph traversal is one of the substantial problems.

### What must be proved

The proof should establish ownership safety, nonduplicated credit, conservation of remaining work through cascading releases, and preservation across function calls. It must account for temporary/stack owners without keeping expired stack addresses. Then it must connect source summaries to emitted operations and runtime work units. Finally, under stated arrival and service assumptions, it must establish a physical storage or capacity bound.

No unconditional theorem can supply finite storage and finite per-action work for arbitrary unbounded arrivals that exceed cleanup capacity. The language must expose an admission condition, backpressure outside protected actions, bounded allocation reserve, or a failure result. A hidden eager drain inside a supposedly bounded callback would invalidate the contract.

Start with an abstract work guarantee. A hardware deadline is a later and different theorem, requiring a specified allocator, bounded copying, backing-free costs, native operations, and execution platform assumptions.

### A decisive first experiment

Build a small explicit-ownership core and an independent work/storage oracle before implementing sophisticated inference. Test nested event scopes, large DAG releases, mixed object sizes, long chains hiding large buffers, stack-owner exits, and allocation-free idle periods. Vary arrival bursts and service, including sustained overload and zero service. Compare the measured complete lifecycle against the predicted bound.

Use current Minyar, eager Minyar, FIFO service, an allocator-driven policy modeled after CTRC, and a simple reserve/admission policy as internal controls. A later external comparison should use the actual pinned CTRC implementation on a mutually expressible subset. Different semantics or representation costs must be disclosed.

**Proceed if** modest source summaries give nonvacuous bounds for several useful program shapes and explain failures outside their assumptions. A new proved guarantee can justify the work even without a universal speed win.

**Redirect if** useful bounds require whole-graph scans on protected paths, multiply all storage by an unrealistic global maximum, or merely restate existing collector-parametric analysis. Event API tests passing would be a prerequisite, not this research result.

## Direction 2 Reuse despite delayed cleanup

### Proposed research claim

Identify conditions under which an allocation can be safely reused when deferred cleanup keeps obsolete physical references alive, without draining those unrelated references or traversing their graphs. Preserve Minyar's observable shared mutation, and prove a bound on the cost of obtaining and checking the reuse authorization.

This is a sharper problem than adding `rc == 1` reuse. Suppose an unreachable old snapshot still points at an object that is also held by the current computation. The object has multiple physical incoming references, but only one observable owner. A conventional physical-count test may decline a useful optimization. Deferral may therefore make an otherwise effective reuse rule less effective.

That example is a hypothesis to measure, not evidence that it dominates Minyar workloads. Moreover, an unreachable object already queued for partial destruction is a different case: reusing or resurrecting it would interfere with its outstanding traversal. The initial proposal should prohibit that case.

### Prior art and the exact potential distinction

Beans, Perceus, frame-limited reuse, and FIP occupy most ordinary uniqueness/reuse territory. CTRC already runs with reuse and distinguishes physical delayed counts in its formalization. First-Order Laziness supplies another neighboring reuse treatment. CIRC addresses consequences of delaying reference operations in a concurrent setting. [Perceus](https://www.microsoft.com/en-us/research/uploads/prod/2021/06/perceus-pldi21.pdf), [FIP](https://webspace.science.uu.nl/~swier004/publications/2023-icfp.pdf), [CIRC](https://www.microsoft.com/en-us/research/publication/concurrent-immediate-reference-counting/)

**Unresolved novelty question:** is there a stronger, economical reuse permission for Minyar's particular combination of observable mutable sharing and delayed owning edges? The distinction between observable and physical ownership is not itself new. The candidate contribution would be an algorithm and proof that exploit it under conditions the closest systems do not already exploit.

### Candidate mechanisms and failure modes

Investigate static ownership evidence that a consumed input has no other observable aliases, potentially supplemented by a generation-checked reuse token. A token is only meaningful if the compiler proves how it was created, where sharing invalidates it, and why every reachable alias is represented. Reentrant native calls, views, stores into containers, and escaping results must participate in that reasoning.

Retired incoming edges also matter after reuse. Later decrements from an old snapshot cannot corrupt the replacement allocation's count or refer to released storage. A generation mechanism, separate retirement state, or an explicit transfer of bookkeeping obligations would need a proof and a measured metadata cost. Merely ignoring those edges would be unsound.

Begin with statically proven isolated transformations and extend only after their semantics are clear. The compiler can retain ordinary physical-count behavior elsewhere. Constant-time permission checking is valuable only if generating the evidence did not insert an unbounded operation into the critical path.

### A decisive first experiment

Construct snapshot replacement, shared DAG updates, parser/tree rewrites, and buffer pipelines. Include a positive case with inaccessible aliases awaiting cleanup and a negative control with a live observer that must see the original object. Measure how often physical counts inhibit reuse at budgets 0, 1, 8, and 32; then compare conservative static ownership, eager RC with reuse, CTRC with its existing reuse, and any proposed rule.

Count allocations and bytes copied, retained physical storage, cleanup work, and the full event/recovery lifecycle. A faster event that transfers a larger bill to recovery is a tradeoff, not a free improvement. Include allocator address reuse and delayed decrements in the safety oracle.

**Proceed if** lost opportunities are common enough to matter and a locally checkable rule recovers them without invalidating observations or the cleanup contract.

**Stop or merge into direction 1 if** the closest CTRC/reuse mechanism already obtains those opportunities, metadata costs erase the benefit, or safe authorization requires draining the dead graph. This is the shortlist's most uncertain implementation idea.

## Direction 3 Inferred acyclic mutation with greater precision

### Proposed research claim

Infer modular reachability/freshness summaries that admit a useful class of safe mutations rejected by Minyar's declared type-graph restriction, while proving the owning heap acyclic and keeping inference within an explicit complexity policy.

The motivating case is inserting a freshly built leaf into an existing recursive structure. A declared-type rule may reject it because a `Node` type can reach another `Node`. A sufficiently precise value-level fact can instead show that the inserted value cannot reach the destination. The fact must include the leaf's fields: newly allocating a wrapper whose field already points to the receiver does not make insertion safe.

The general insertion condition is that adding `receiver -> value` cannot close a path `value -> receiver`. Acyclicity of each operand separately does not imply this condition. Shared DAGs are allowed, and disjointness is a sufficient but sometimes unnecessarily strong approximation.

### Prior art and what could remain new

Reachability/cyclicity analyses, region typing, freshness qualifiers, bidirectional inference, and ownership transfer effects already address closely related information. [Lu and Potter](https://cgi.cse.unsw.edu.au/~reports/papers/0434.pdf), [field-sensitive reachability](https://arxiv.org/abs/1306.6526), [polymorphic reachability types](https://arxiv.org/abs/2307.13844)

The candidate result must show a new useful precision/complexity point for an acyclic mutable owning language. It might combine cheap declared-type rejection/acceptance rules with more precise flow summaries only where needed. A claimed improvement must be assessed against the recent reachability work, not only against Minyar's current restrictive checker.

### A plausible initial discipline

Track a finite set of abstract allocation/ownership regions, fresh-result facts, and field-sensitive possible reachability. Function interfaces describe input/output relations and mutations. The current declared-type rule remains a cheap sufficient condition where applicable; a more precise rule handles otherwise rejected operations. When evidence is unknown, reject a protected mutation or require an explicit alternative operation. Do not silently copy, because aliases would then observe different behavior.

Facts must be invalidated by updates and escaping references. A function returning a fresh allocation may still return something that reaches an argument. Polymorphic container operations need summaries that preserve that distinction. Recursive calls and module cycles require a conservative fixed point. A native function without an adequate summary cannot be assumed harmless.

Every new accepted owning edge needs a sound proof rule. Safe construction, subtree reattachment, two separately built DAGs, repeated aliasing, field replacement, and storing a receiver beneath its descendant should all be considered explicitly. An optional explicit weak/non-owning reference design would be a separate semantics and safety project, rather than an invisible exception to owning acyclicity.

### A decisive first experiment

Curate a corpus of currently rejected but manually proven safe programs and unsafe programs that look similar. Include graphs with shared children and wrapper allocations containing back-references. Compare acceptance precision, required annotations, analysis work, summary size, and generated RC operations against the current rule and a straightforward richer reachability analysis.

For the first-order core, mechanize preservation of owning acyclicity. Separately measure inference on increasingly large recursive module groups and adversarial graphs of type/summary constraints. A time budget may trigger a conservative unknown result, but it must not trigger unsound acceptance or unstable cached conclusions.

**Proceed if** the analysis admits useful mutations with small stable summaries and a sound modular proof, offering a material precision or compilation-cost advantage over a credible adaptation of prior work.

**Redirect if** the accepted cases are only trivial wrappers, require extensive lifetime annotations, or match an existing reachability system with no additional guarantee. Merely weakening the current rejection rule is language improvement, but not necessarily publication-level novelty.

## Direction 4 Layouts chosen for locality and reclamation

### Proposed research claim

Infer representations or region partitions that optimize locality while respecting a proved bound on cleanup work and retained capacity, including shared mutable identity. Choose where to use individual objects, packed buffers, and region boundaries based on both access patterns and ownership obligations.

This would connect language representation, allocation, and resource contracts. For example, a batch of private tree nodes might be stored together, while shared boundary nodes remain separately identifiable. The partitioning must preserve which aliases denote the same object and which writes other aliases observe.

### Prior art makes this a demanding project

Marmoset already optimizes recursive layouts using constraints; SoCal already factors layouts across buffers. LoCalMem's boundary types and update bounds are especially close to a representation with explicit boundaries. Region capability systems provide another foundation. [Marmoset](https://arxiv.org/pdf/2405.17590), [LoCalMem](https://kar.kent.ac.uk/116036/), [Reference Capabilities](https://arxiv.org/abs/2309.02983)

**Unresolved novelty question:** can a new partitioning or inference algorithm jointly guarantee cleanup granularity and capacity while retaining observable mutable identity? Existing pure-value results cannot simply be assumed to cover it, but mutation alone is not a sufficient novelty distinction.

### The hard boundary case

Releasing a region is not automatically one unit of work. It may contain many outgoing owning edges, finalizers, or buffers whose backing release is costly. Skipping internal reference decrements is useful only if boundary obligations remain accounted for. Shared objects can also escape and prevent the region from being released as a whole.

Thus each proposed representation needs a layout/ownership semantics, a bound on its outgoing work, and an allocator model. Native interoperability may require pinned representations or wrappers at explicit boundaries. Runtime representation switching must not perform a hidden large copy in a protected action.

### A decisive first experiment

Use mutable scene/AST DAGs, immutable snapshot subgraphs with mutable boundaries, and sequential buffer pipelines. Compare ordinary boxed RC, manual arenas as an upper-bound control, and appropriate packed-layout systems on a mutually expressible subset. Keep algorithm and alias semantics fixed.

Measure cache misses, traversal throughput, allocation/copy traffic, maximum boundary cleanup work, retained capacity, and inference cost. The contribution should be a new proved selection rule or a clear multi-resource result; a fast structure-of-arrays example is insufficient.

**Recommendation:** keep this as a longer project after directions 1 or 3 clarify the ownership/resource IR. It is substantial but architecturally expensive and heavily contested by recent work.

## Direction 5 Checked ownership and cost preserving compilation

### Proposed research claim

Introduce an explicit ownership/resource IR and a small independent checker that validates both safety obligations and preservation of declared cleanup/resource contracts through selected optimizations and lowering to runtime calls.

An optimization can preserve the program's returned value while changing where cleanup occurs, how much storage remains retained, or which callback pays the cost. Moving a release, changing owner-frame representation, or fusing service points can therefore invalidate a resource contract without creating a conventional semantic miscompile.

### Prior art and the specific opportunity

Alive2 addresses LLVM semantic refinement with bounded validation; source/target cost analysis and CerCo address other cost-preservation problems. These supply foundations and comparisons, rather than an unoccupied area. [Alive2](https://users.cs.utah.edu/~regehr/alive2-pldi21.pdf), [source and target costs](https://www.cs.cmu.edu/~janh/assets/pdf/MullerH19.pdf), [CerCo project aims](https://cordis.europa.eu/project/id/243881)

**Unresolved novelty question:** is there a lightweight validation discipline for delayed shared ownership that preserves a compositional cleanup contract across the particular transformations Minyar uses? The desired result is not a claim that all LLVM passes or all hardware execution have verified costs.

### A tractable scope

Start with explicit instructions for retain, transfer, release, owner-frame storage, borrow validity, queued-work service, and allocation capacity. An optimization emits a certificate or a checkable relation between its before/after accounting. A trusted runtime cost model provides operation contracts. The checker must be independent enough to catch emitter mistakes, not recompute a copy of the same implementation decisions.

Prove local transformation preservation for scalar replacement, ownership transfer elimination, frame packing, and movement of releases. Then test the bridge from IR operations to emitted runtime calls. Source contracts also need invalidation when a runtime ABI or policy changes.

A semantic validator can support some low-level steps, but its bounded nature and lack of a resource theorem must remain explicit. The first meaningful result could cover a small verified core and selected transformations, with the rest of the compiler treated as checked or outside the guarantee.

### A decisive first experiment

Seed transformations that return identical values but violate the contract: add an extra nested poll allowance, defer a required stack-owner visit, duplicate a credit, or move a cascade into a protected action. The independent checker must reject them. Measure checker time, certificate size, covered transformations, and resulting program performance.

**Recommendation:** develop this as the proof infrastructure for direction 1. It becomes an independent research project only if the validation method is new and general enough beyond Minyar's current emitter.

## Direction 6 Predictable incremental resource inference

### Proposed research claim

Provide a useful modular ownership/reachability/resource analysis whose incremental reanalysis has a proved work bound expressed in changed interfaces and affected dependency closure, with a conservative fallback when precision exceeds a declared budget.

This is a compiler research problem, rather than a claim about fast self-compilation on one machine. Adding sophisticated inference risks undermining Minyar's current small compiler and predictable engineering budgets. A principled bounded-analysis design could preserve that advantage.

### Prior art and limits of the present review

Incremental dependency management is well studied, and recent preliminary work explicitly studies compile-time guarantees for optimization heuristics. [Build Systems à la Carte](https://www.microsoft.com/en-us/research/wp-content/uploads/2018/03/build-systems-final.pdf), [formal heuristic guarantees](https://arxiv.org/abs/2608.20137)

This branch received a lighter audit than memory/reachability. Incremental type checking, dynamic dependency discovery, abstract interpretation convergence, and bounded solver methods need a deeper review before it should be promoted to the main novelty claim.

### What the result would need

Account for summary size and fixed-point work, not just changed source length. A body change that preserves its exported resource summary should permit early cutoff. A changed transitive summary legitimately affects callers. Some global changes can require full reanalysis, and a theorem should expose that rather than hide it in averages.

Specify whether sources must still be read, which native/package changes invalidate inference, and which costs belong to external LLVM optimization and linking. Minyar's current incremental path still reads reachable inputs and invokes native tooling; the current module cache does not establish a sublinear total build theorem. See [incremental builds](../../docs/incremental-builds.md).

An analysis budget needs deterministic conservative behavior. Cached facts cannot depend unsafely on whether a prior run exhausted a different amount of time. A separate checker could validate summaries so that bounded inference and soundness are not tied to one heuristic's success.

### A decisive first experiment

Generate chains, stars, and strongly connected module groups with large summaries. Exercise private body edits, stable-signature edits, resource-signature changes, and worst-case invalidation. Measure total constraint work, summary bytes, source reads, invalidated modules, and external compile/link cost separately.

**Recommendation:** treat this as an engineering constraint on directions 1 and 3 initially. Pursue it independently only after identifying a new complexity/precision result against the deeper incremental-analysis literature.

## Direction 7 Concurrency and cycles

These are possible substantial projects, but neither is a cheap novelty extension.

For concurrency, a potentially interesting target is composition of per-task cleanup obligations through ownership transfer, including migration of outstanding debt and a proved aggregate capacity bound. The transfer protocol would need bounded synchronization and clear atomic ownership transitions. ORCA, reference capabilities, and CIRC already occupy much of actor isolation and concurrent RC. [ORCA](https://www.ponylang.io/media/papers/orca_gc_and_type_system_co-design_for_actor_languages.pdf), [CIRC](https://www.microsoft.com/en-us/research/publication/concurrent-immediate-reference-counting/)

For cycles, a potentially interesting target is incremental graph maintenance with a useful bound on detection/reconnection work and retained space. Arborescent collection is a close dynamic-graph precursor; immediate discovery/reclamation should not be equated with bounded work. [Arborescent GC](https://oestoleary.com/papers/ISMM25.pdf)

Both directions would change the central assumptions that currently make Minyar's ownership/runtime tractable. They require safety, scheduling, and space arguments beyond the single-mutator DAG case. **Recommendation:** preserve the current scope for the first research result. Revisit these after the contracts and IR are established, rather than adding them to make the language appear more novel.

## Other language features and research value

The whole-language review does not imply that every feature needs its own novel algorithm. Syntax, checked arithmetic, Unicode behavior, error diagnostics, native bindings, package interfaces, and bootstrap stability can make Minyar useful without constituting new research. The present evidence does not support independent novelty claims for those features.

They can nevertheless influence the main research problem. Bounds must include or explicitly separate copying, Unicode scanning, collection growth, exceptional/trapping exits, and native operations. A contract cannot silently assume an error path performs no cleanup. Native code that creates aliases or retains storage must expose an adequate summary or lie outside the proved interface.

Ergonomics is also measurable. A language-design result should evaluate annotation burden, accepted safe programs, and whether users can understand a rejected contract. A new lifetime syntax would be a weak research aim; a precise inferred guarantee that programmers can use with modest annotations would be stronger.

Mutable value semantics, borrowed modes, regions, and capabilities are alternatives or ingredients. They should be introduced because their semantics solve a specific problem, rather than assembled into a novelty claim based on the language having a unique feature list. [Mutable Value Semantics](https://research.google/pubs/mutable-value-semantics/), [OxCaml modes](https://oxcaml.org/documentation/modes/intro/)

## Comparing the directions

The judgments below are qualitative assessments of this evidence, not probabilities of publication.

| Direction | Prior-art pressure | Main theoretical difficulty | Main implementation dependency | Priority |
| --- | --- | --- | --- | --- |
| Cleanup and retained-memory contracts | High; several fields intersect | Sound delayed obligations plus service/capacity composition | Explicit accounting IR and event integration | Main project |
| Reuse during deferral | Very high | Permission validity and retirement bookkeeping | Reachability/ownership evidence | Focused falsification pilot |
| Permissive acyclic mutation | Very high and active | Precise modular reachability with sound invalidation | Typed IR and summaries | Strong independent option |
| Reclamation-aware layouts | Very high and active | Representation identity plus boundary cleanup bound | Region/layout compiler and ABI work | Longer project |
| Checked cost-preserving compilation | High | Resource preservation through optimizations | Explicit IR and independent checker | Enabling project |
| Predictable incremental inference | High; audit incomplete | Precision, convergence, and invalidation complexity | Stable module summaries | Constraint first |
| Concurrent debt or bounded cycles | Very high | Global progress/capacity plus synchronization/graph work | New ownership/runtime semantics | Defer |

The most coherent broader language identity would be: **ordinary shared mutable programs, with inferred or checked guarantees about where memory-management work occurs and what capacity it requires**. This is a proposed research goal. A finished claim should name the accepted subset and its exact guarantee, rather than promise unrestricted programs with no pauses and no overhead.

## A concrete research sequence

### First establish the exact claim

Write a one-page statement for direction 1 with the operational units, heap assumptions, accepted source subset, and required service policy. Draw a direct correspondence to CTRC, GC-space analysis, real-time scheduling, and reactive typing. Obtain the inaccessible close papers identified in the source register before declaring priority.

Pin the relevant runtime/compiler versions and external artifacts. Use the existing event acceptance requirements as implementation requirements, not as a proxy for the research theorem. Keep its stringent comparative gates separate from a paper's narrowly justified guarantee: a new guarantee does not require beating every baseline on every metric.

### Then test the difficult accounting cases

Build an independent abstract machine and compare it with real-runtime traces. Start with the hidden large descendant, shared DAG, nested scopes, mandatory stack exit, and mixed-capacity examples. Try to falsify any simple proposed potential before building inference.

The decision is whether a compact, maintainable resource model can predict useful bounds without a graph scan. If it cannot, narrow the source subset or switch to the more precise mutation project. Do not spend months polishing a scheduler before knowing what theorem it could support.

### Add a small inference and preservation result

Introduce a typed ownership/resource representation for a first-order core. Infer summaries for a deliberately selected set of constructors, calls, bounded loops, and container operations. Mechanize the core safety/accounting proof or use an independent checker with a clearly stated trust boundary. Expand the language only after the core contract survives emitted-runtime comparison.

This stage should produce a useful artifact even if the broader ambition is too hard: a precise fragment, a reproducible implementation, and explicit cases that remain unknown. Avoid claiming inference completeness when conservative fallback is part of the design.

### Evaluate the full lifecycle and the tradeoff

Use at least four distinct workload families: persistent snapshot replacement, mutable DAG manipulation, streaming buffer/text pipelines, and ongoing event loops with bursts/recovery. Include adversarial microcases separately from representative applications. Verify identical outputs and relevant alias observations.

Compare pinned implementations and disclose different restrictions. Measure response tails, mandatory and queued work, dead/live/backing storage, owner metadata, allocation/copy volume, and complete setup-to-teardown service. Vary sizes, sharing, budget, arrival/service ratio, allocator, and hardware where appropriate. Keep timing and diagnostic instrumentation separate but correspondence-checked.

Predeclare performance hypotheses and useful effect sizes for each workload. Report uncertainty and all workload/baseline failures. A possible selection gate could be a material retained-capacity reduction at equal service assumptions, but its threshold must be chosen before observing the candidate results; this report predicts no such reduction.

The current study's three seeds and one synthetic application are starting evidence. They cannot establish rare-event behavior, overload stability, universal superiority, or the cause of millisecond outliers. New testing should resolve a named uncertainty rather than accumulate more repetitions of the same narrow case.

### Frame the result around the achieved guarantee

If successful, a defensible paper claim might be:

> For a specified class of shared mutable acyclic programs, compiler-checked resource summaries and a service protocol bound mandatory management work and deferred retained capacity, and the guarantees are preserved by the implemented lowering.

That sentence describes a target, not an existing Minyar result. It would need to become more precise and be checked against the closest literature. If the actual achievement is instead a new reachability analysis or reuse algorithm, frame the paper around that result and its limitations.

## Judgment on the existing research

The existing formal model, counterexample, runtime correction, and reproducible studies are valuable preparation. They demonstrate that the implementation has measurable contracts worth studying. They do not yet establish a publication-level novelty result.

The broad memory-management idea has predecessors. The work is still useful because it provides a concrete language and runtime in which stronger questions can be tested. My recommendation is to turn the current per-batch accounting into a **proved compositional work-and-capacity model**, while running small falsification pilots for deferred reuse and more permissive acyclic mutation. That gives Minyar a substantial research question with clear failure conditions, rather than a novelty claim based on its implementation being individually unusual.
