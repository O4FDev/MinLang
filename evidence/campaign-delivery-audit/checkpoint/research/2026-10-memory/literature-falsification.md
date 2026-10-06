# Mechanism and novelty falsification matrix

Review started 4 October 2026. This is a research decision record, not a novelty certificate. The source register and search limitations are in [literature.md](literature.md). Proposed experiments are prospective until linked to actual evidence. They preserve existing source syntax and shared observable mutation.

## Decisions that the literature already settles

The closest comparison is [CTRC](https://lptk.github.io/files/ctrc-2024-05-09.pdf): uniform cells, deferred outgoing drops, allocation-time reuse, and an eager/lazy count relation. [RTRC](https://www.diva-portal.org/smash/get/diva2:743471/fulltext01.pdf) already divides objects into equal blocks and schedules pre-decrement work. Neither bounded destruction nor equal-size segmentation is an unoccupied research claim.

[Frame-limited reuse](https://www.microsoft.com/en-us/research/uploads/prod/2021/11/flreuse-tr.pdf) makes retention an explicit proof obligation. Section 4.2 shows that unrestricted borrowing can retain arbitrarily more memory; its drop-guided reuse analysis controls additional retention per evaluation context. This report was accessible in full during this campaign, closing an access gap in the earlier survey.

## Exact candidate mechanisms

| ID | Mechanism under test | Strongest disconfirming baseline | What could still be an additional result | Decisive negative outcome |
| --- | --- | --- | --- | --- |
| F01 | Earlier retirement of compiler-known last-use local roots | Perceus; conventional liveness and ARC optimization | Preservation for Minyar's effectful argument evaluation and incremental owner queues, with a measured useful reduction | Only trivial dead locals improve; borrow protection or alias mutation breaks; existing lowering already retires equally early |
| F02 | Last-use transfer of caller ownership into a callee whose parameter is currently borrowed | Beans, Perceus, frame-limited borrowing, Morphic | A controlled tradeoff between RC traffic, reuse eligibility, and retained bytes for shared imperative semantics | Space improves only by adding more critical-path work; a standard consuming-call transform is equivalent |
| F03 | Recover uniqueness after dead owner storage has been deferred | CTRC's lazy reuse; precise RC reuse; eager cleanup | Safe useful reuse under a strict small service allowance without scanning/draining unrelated owners | Locating dead incoming edges needs an unbounded search; correctness requires treating alive aliases as dead; overhead exceeds saved copies |
| F04 | Exact synchronous retirement for small fixed owner frames, selected from remaining K | Existing Minyar admission rule; root scanning and stack RC optimization; Work Packets task unification | A compositional rule sharing an outer allowance across nested calls and proving mandatory-owner work plus service | Inner scopes replenish allowance; expired stack storage enters a queue; benefit disappears against a fixed threshold |
| F05 | Byte- and work-sensitive reclamation admission | Boehm lazy-RC space limits; GC heap-space analyses; network calculus | A source-to-actual-capacity certificate covering hidden descendants, pool rounding, roots, caches and transient resize storage | Certificate ignores descendants or double buffers; assumptions require inspecting the entire graph on the critical path |
| F06 | Fixed-cell representation only for statically small records | Baker, RTRC, CTRC; pool/size-class allocation | Automatic representation choice with an actual cost/space crossover and preserved mutation/FFI behavior | Improvement is just allocator selection; pointer indirection or fragmentation dominates; target bounds exclude important operations |
| F07 | Freshness proof admitting currently rejected acyclic recursive mutations | Reachability/acyclicity types, shape analysis, freshness inference | A deliberately small modular inference with a useful expressiveness/compile-time boundary | Fresh child reaches receiver through constructor arguments or effects; accepted safe programs are too rare |
| F08 | Inferred stack/region storage for nonescaping managed objects | Tofte–Talpin, Cyclone, ML Kit, ASAP, escape analysis | Automatic destruction/accounting compatible with outgoing managed edges and deferred cleanup | Escaping interior projection outlives stack object; last owner must be visited after stack expires |
| F09 | Recycling detached temporary-owner chunks | Established object caches, arena reuse, current frame cache | A reduced constant factor with an independently enforced byte cap | Stable workloads only benefit by increasing retained memory; outstanding chunk lifetimes alias recycled storage |
| F10 | Event-local debt service or idle recovery | Metronome, time-triggered GC, tax-and-spend, Go pacing/assists; event memory/scheduler co-design 2006 | One shared allowance across lowering and runtime with explicit recovery/capacity assumptions | Average service covers demand but bursts exhaust capacity; quiet windows begin nearly debt-free |
| F11 | Add cyclic graph support with local cycle collection | Bacon–Rajan; Nim ORC; CIRC/CDPT; rust-cc; immutable SCC counting | A precise new bounded interface plus useful semantics | Local candidate cycle can contain arbitrarily many nodes; trial deletion or SCC preparation exceeds allowance; resurrection/reentrancy invalidates invariants |
| F12 | Arena-style snapshot replacement | Region systems; manual C++/Rust/Zig arenas; graph IDs | An inferred safe region boundary with explicit cross-boundary owner accounting | Cross-snapshot aliases force retention of whole arenas; arena reset traversal hides graph-sized drops |

F01, F02, F08 and F09 are reasonable engineering experiments even when their broad research claim is already occupied. Publication should follow a proved extra guarantee or a substantial new measured tradeoff. F03 and F05 have the clearest connection to Minyar's specific delayed-owner behavior, but carry higher correctness or proof risk.

## Experiment cards for the active engineering work

### E01 Deferred owners and consuming Text joins

Hypothesis: a logically dead alias in a detached owner frame or retired container keeps the physical count above one and forces a copying fallback in the existing consuming Text join. Measure that effect before designing another count representation.

Use one generated workload and independently vary only eager versus incremental retirement, then K1/K8/K32. Build a mortal owning Text outside the integer cache and retain a second alias in a helper's owner storage. Leave the helper or discard its containing object, then repeatedly perform the existing direct `text = text + piece` operation. Sweep prefix size, piece size, alias count, dead-owner backlog, and gap between retirement and join. Include matched fully drained controls and no-alias controls.

Record reuse attempts/successes, copying fallback count, bytes copied, requested and rounded managed bytes, pending work, owner visits, and peak live-root bytes. Hash output after every join; keep a live alias that checks the original immutable bytes. Include self-concatenation, a slice view of the left side, RHS callbacks mutating/replacing a shared binding, and multiple dead roots separated by unrelated queue tasks. Timings and diagnostic counters should use separate binaries if instrumentation perturbs the path.

Failing first tests should exhibit the missed reuse and demonstrate the alive-alias/self-alias hazards. A proposed change must pass those tests and the existing budget oracle before performance runs. An experiment showing missed reuse supports a cost mechanism; it does not justify reducing rc without proving which incoming owners are unobservable.

### E02 Borrowed caller roots and memory growth

Hypothesis: retaining each caller's old argument during a recursive transformation can keep old large graphs alive while fresh output is allocated. The relevant precedent is the borrowing counterexample in frame-limited reuse, not a claim that borrowing is unsafe.

Construct a recursion or nested-call family with a large input per depth. Each callee observes its input, creates the next large input, then calls again; the caller never observes the old input after the call. Sweep depth and input bytes separately. Include a transformation with no new managed allocation, an alive caller alias used after return, a shared mutable payload updated through the callee, and a returned borrowed child. Compare the existing borrowed-call policy with an experimental last-use transfer and an eager policy using identical source and compiler optimization settings.

Count active caller-root bytes separately from queued retirement bytes. Otherwise a liveness problem can be incorrectly attributed to scheduler fairness. Report stack space too: source tail recursion does not imply generated tail calls. Use bounded depths under sanitizers and independently inspect generated LLVM call/return ownership.

An earlier root release is invalid if the callee has only a borrow after the caller's sole protecting owner disappears. A correct transfer must establish callee ownership or prove another owner protects every interior borrow through all effects and return paths. Give the transfer an explicit compiler-only state and a conservative fallback; no source syntax is required.

### E03 Hidden large descendants and recovery under overload

Hypothesis: small measured queue debt can conceal large retained storage behind unprocessed owning edges. Build a small retired ancestor chain ending in a large leaf allocation. Mix it with new short-lived objects, detached owner frames, and temporary chunks. Repeat the same shape at several chain depths and leaf sizes.

An independent allocation ledger should classify physical bytes as reachable from active roots, retained solely by deferred edges/roots, cached, and free. Work units and bytes must remain separate. Compare current, FIFO, simple fair-unit, LIFO and eager controls with the same generated program. Keep a permanently alive shared descendant to check that physical reclamation does not treat all dead-parent edges as independent garbage.

Choose arrival envelopes before measurement: subcritical, at service capacity, burst then recovery, and sustained overload. Start quiet windows with a declared amount of debt, not merely whatever debt remains after a light workload. Report peak physical capacity, failures, completed arrivals, response time including waiting, recovery time, and remaining debt. An overload failure is a result, not an invalid run. The same finite-heap failure policy must apply to every schedule.

### E04 Frame size and effective event allowance

Hypothesis: a per-hook K bound can accumulate much more cleanup during one event and leave too little allowance for mandatory stack-owner visits. Generate nested helpers, many small statements, loops, early returns and mixed heap/stack ownership frames. Track every service call in an independently defined event span.

Compare the current per-operation K policy with a prototype shared allowance only if the parent chooses to implement one. The oracle must count immediate leaf destruction, owner visits and task completion, and separately count excluded copies, initialization and allocator operations. Test K1 and boundary frame sizes K−1/K/K+1. A stack lifetime test must fail any implementation that defers visits by queueing addresses inside an expired activation.

No scheduler alone can promise a time deadline while arbitrary Text growth, List copying, frame initialization and foreign calls remain admitted. The event contract should state exactly which work it limits and which source-to-runtime assumptions it checks.

### E05 Simple freshness and no-cycle counterexamples

Prototype an analysis only after establishing useful rejected programs: fresh leaf insertion into a recursive List; bottom-up tree builder; field replacement with a disconnected child; shared DAG attachment. Compare each with the existing pure-construction/`appended` form and count resulting allocations/copies.

Negative corpus: append receiver through a fresh wrapper; append fresh node whose child already aliases receiver; return value from effectful helper retaining receiver; mutation through alias inside constructor argument evaluation; nested List types; mutually recursive record types; safe then unsafe mutation after freshness escapes. Whole-object identity being fresh does not prove its reachable graph excludes the receiver.

Measure accepted useful patterns, false rejections, inference steps and maximum metadata. Soundness requires proving absence of the return path at every admitted insertion, preserving it through effects and module summaries. An unrestricted runtime reachability scan is an unsuitable fallback for a critical path.

## Priority check before claiming an extra result

For the final mechanism, search the exact theorem and synonyms, read the closest full text and its references, follow recent citing work, and compare assumptions line by line. The searchable phrases should include dead roots, stale reference counts, deferred decrements, delayed uniqueness, lazy reuse, root reconciliation, last-use transfer, space-safe borrowing, bounded RC, collector-sensitive heap analysis and byte debt.

Reject a proposed novelty claim if a preceding system already proves the same property under assumptions at least as useful. Retain an engineering improvement under an accurate name. Absence of an exact phrase in a search result is insufficient evidence of priority.
