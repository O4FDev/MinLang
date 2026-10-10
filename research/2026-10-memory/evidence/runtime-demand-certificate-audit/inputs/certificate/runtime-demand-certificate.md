# Representation-aware future cleanup demand: conditional result and rejection

**Result.** A precise closed-cohort certificate exists for the supported subset below. Without mortal Text, its scan-and-task sum equals remaining reported structural cleanup work, even for shared DAGs. With flattened Text, the same sum plus one token per remaining owning Text is a sound upper bound; exact demand additionally depends on which kind of owner drops the root last. A two-slot, hand-derived counterexample rejects an exact certificate based only on aggregate representation counts. Reserving all reference-List slots before first-mortal promotion avoids prefix undercharging, but can overestimate the saved immortal-only case by tens of thousands of units. This is a conditional representation theorem, **not verified C/compiler correctness, a new lazy-RC technique, an allocation-admission certificate, or a production proposal**.

Method: source and saved-record reading, filesystem copies/hashes, and hand reasoning only. No Minyar/native programs, tests, compilers, models, installations, commits, subagents or timing experiments were run. Only this report, its JSON, and `evidence/runtime-demand-certificate/` were written. Stopped execution lanes remain stopped. The campaign is not complete; its earliest finish remains **2026-10-04 06:54:29 UTC**.

## Frozen inputs and reading extent

[Input copies and SHA-256 manifest](evidence/runtime-demand-certificate/inputs.sha256) pin eight current runtime files, nine saved research/evidence records and the previously accessible CTRC text. The current core hashes match the accepted patch inventory and admission audit:

| Source | SHA-256 |
| --- | --- |
| `minyar_runtime.c` | `c4e78f59096e0af8926c8d06febb9277e8c7cb7e5de8fc63b907d3afb613fcb4` |
| `minyar_bounded_rc.h` | `7d40e4f2469150840b4527a85f4234a677ed177803793372fd4104b0e8e7304e` |
| `minyar_rc.h` | `5d57a4494b2dc244d279ce8fbd50101184e1a7b46215f3c51f35766d4fccef9b` |
| `minyar_collections.h` | `01ae1e88dbcd98a9f8815a7a8e0508247a19f7f0b912d938544db129191eb4c0` |
| `minyar_pool.h` | `487b8f8d802896c365b0177f46795ecf1b479d7048ff5033a24f08617de6e2fd` |

Repository README, architecture, runtime contracts, campaign README, hardening notes, round-two literature claims/H2, accounting/source-map/model result, formal proof sketch, completed native-model design/report, retirement/Bytes rejection, ABI map, transformation and admission reviews, view/cache count probes and actual RC/heap/pool/collections/stack fragments were consulted. The fragments governing this theorem were read completely; the main translation unit was read selectively for layout, allocation, Text construction/index/view, cache and raw-path boundaries. Large notes/evidence records were read selectively, not credited as exhaustive audits. The old accounting model's main-runtime hash is `db41660...`, not the frozen `c4e78f...`; its scoped slice fingerprint is historical evidence, not a current whole-source verification.

CTRC was reread from saved primary text: §2.3's layout/segmentation ending on printed pp 7–8, §2.4 pp 8–9 and §2.5 pp 9–10. Appendix proofs and evaluation were not newly audited. Collector-sensitive analysis/AARA comparisons below inherit exactly the limited readings in the existing registers. No new web retrieval was necessary; excluded Rust, university and Joisha routes were not accessed or retried. [Reading ledger](evidence/runtime-demand-certificate/reading-ledger.json) records these limits.

All source line references below refer to frozen copies in [the runtime input directory](evidence/runtime-demand-certificate/inputs/runtime/).

## Supported subset and closure boundary

Use the supported 64-bit, non-arena incremental runtime, one mutator, successful finite allocations, correct owner counts, acyclic managed ownership, non-reentrant runtime/allocator hooks and no finalizers/weak owners. Ordinary records have fixed arity at most A, Lists have length at most L, and the cohort has finitely many allocation generations. A and L alone do not bound the number of generations. Text has truthful metadata and flattened owning/immortal roots. Pointer tagging, cursor encoding and all integer counters remain representable. These are premises, with implementation obligations below.

At a public boundary t, there is no unregistered producer, ownership token in flight, partially initialized aggregate, foreign-held mortal owner or unmodelled external root. Every mortal root belongs to an active/retired frame or temporary chunk. Borrowed parameters have their protecting caller owner in that set. All mortal allocated objects, including positive-count descendants held by unvisited retired slots, belong to the cohort. Existing runtime immortals are owning Text/cache/literal leaves, not immortal containers hiding mortal children.

After t, perform only matched retirement of the already active frames/chunks and positive-budget cleanup until drained. No constructors, new keep/borrow/local owners, slot replacements, appends, cache growth, Text indexing/joins, new frames or raw allocation requests occur. Stack frames leave while their supplied storage is valid; heap frames may enter the existing empty-frame cache. The closure protocol must offer service after all roots are detached; an empty queue while an active frame still owns objects is not completion. Cache disposal is outside the structural-work count. Supported cached immortals and empty cached frames remain retained.

Bytes, file/native staging, compiler arenas, foreign graphs and unrelated raw pool blocks are excluded from the managed cohort. A whole-pool storage assertion must nevertheless include any such blocks as an explicit outside charge; the demand theorem supplies no license to omit them. Bytes shares the Text leaf kind/layout but is not typed Text, so its capacity field must not be interpreted as a character certificate.

The subset admits shared descendants, ordinary safe mutable records/Lists before t, mixed scalar/reference record slots, immortal-only List prefixes, already active/retired owners, partially serviced object tasks, and both batching paths. It does not silently assume unique children or queue-empty state.

## Source lemmas and the exact demand identity

Define these semantic quantities at t, each over allocation identity, not root-to-node paths:

* **V:** all remaining required visits. A live, nonempty `RC_RECORD` contributes its whole arity, including scalar/unset map entries. A live, nonempty `RC_REFERENCES` List contributes its whole length. A retired aggregate contributes length minus its semantic cursor. Active heap/stack frames contribute `written_count`; detached heap frames contribute remaining `local_count`. Active chunks contribute their occupied counts (equivalently frame `temporary_count`); detached chunks contribute remaining `count`. Moved/null sparse local entries still contribute visits. Do not count chunk slots twice through their frame.
* **F:** one remaining finalization for every nonempty reference record/List, every active/retired heap-frame activation, and every active/retired temporary chunk. A cached frame contributes zero. A stack frame contributes zero finalization. Scalar records/Lists, empty reference aggregates and immortal-only Lists contribute zero: their destruction is folded into the visit that drops them.
* **Q:** owning Text roots already queued as fieldless tasks.
* **R:** still positive-count mortal owning Text roots, each counted once. Views contribute neither Q nor R; their backing edge is decremented inline. Immortals contribute zero.

These definitions concern *remaining cleanup units*, not scalar work, number of managed destructions or allocator calls.

| Lemma | Frozen source and consequence |
| --- | --- |
| L1: exact scan extent | `minyar_bounded_rc.h:142–155,169–183`: reference Lists visit every length position; reference records visit every arity position even when map bit is zero. Each advances one cursor. `45–66,157–159,187–190`: finalization is a separate unit. |
| L2: inline leaves | `minyar_bounded_rc.h:77–114`: scalar records, scalar/immortal-only Lists, empty reference aggregates and Text views/ordinary owning Text can finish inside a dropping visit. A slot visit is charged once even when it destroys a leaf. Adding another finalization for every allocated leaf double-counts operational units. |
| L3: Text exception | `minyar_bounded_rc.h:92–105`: the last view can decrement and enqueue its root without a second destruction. `minyar_runtime.c:816–835` ensures backing is a flattened owning or immortal root. Queued roots require exactly one later task-finalization unit. |
| L4: owner storage | `minyar_rc.h:35–50,65–73,305–316,327–346,362–386` and `minyar_bounded_rc.h:121–129,219–250`: sparse visits, full/partial chunks and heap-frame/chunk finalizations are separate. Moving a local clears its owner but preserves its indexed visit. Detachment transfers obligations; it does not create new object work. |
| L5: stack distinction | `minyar_stack_frames.h:24–38,46–64`: actual stack representation has written visits, no queued header finalization/cache entry. Fallback is an ordinary heap frame and must be counted as such. |
| L6: batching refinement | `minyar_bounded_rc.h:269–315,326–348`: a unary pair costs two; carrying a child consumes its existing visit/finalization obligations; List batches count each slot and stop on new recent work. Inside a fused pair, use the C-local carried child with semantic cursor zero, not a scanner of transient globals. |
| L7: no hidden duplicate object | Correct owner conservation plus acyclicity implies every mortal object eventually loses its last owner during complete closure. Its reference aggregate is scanned/finalized once regardless of fan-in. Counts/queues do not make a shared child into multiple allocations. This is the existing accounting premise, not a newly proved compiler fact. |

**Conditional theorem.** Assume L1–L7 are faithful refinements of every actual transition and all closure premises hold. For a complete closure execution σ, let δ(r,σ)=1 exactly when a currently positive-count owning Text root r loses its last owner through destruction of a view, and zero when its last owner is dropped directly by a visited frame/chunk/aggregate slot. Let W be the sum of reported queued work and charged synchronous stack-owner visits after t. Then:

```text
W(σ) = V + F + Q + Σ[r in remaining owning Text roots] δ(r,σ)

V + F + Q <= W(σ) <= V + F + Q + R.
```

Consequently **W=V+F** when there is no mortal Text, and **W=V+F+Q+R** when every still-live mortal owning Text has only view owners at t. The latter is an extra ownership premise, not something inferable from `backing==NULL` or a reference count alone. The bounds are attained by the small Text counterexample below. The identity is schedule-dependent through δ; the upper bound is not.

Proof: give each required visit and each separately finalized task one ticket. An ordinary scan or owner unit consumes one visit ticket; an ordinary task finalization consumes one finalization ticket. Last-owner leaf destruction adds no ticket/unit beyond its dropping visit. Every last-view root decrement creates one root-finalization ticket, already budgeted by that root's R token; an initially queued root uses Q. Unary fusion consumes two tickets per pair, including its carried child, and List batching consumes one per visited position. No new allocation or mutation can introduce obligations after t. Every allocated mortal object is accounted for once, so hidden descendants and shared nodes cannot increase the sum on enqueue. Owner conservation, finite acyclicity and continued service ensure complete discharge; summing the local identities gives the equation. This specializes the existing closed-phase argument by identifying *operationally cocharged leaves* and the exact Text correction. It is not an open-arrival theorem.

## Tightness rejected by a two-owner Text counterexample

Take system or fixed K1, no preexisting debt/cache, one heap frame with two written local slots, one owning ASCII Text R with byte length 8, and a proper six-byte view V. The root is small enough to take the actual view path, not the tiny-slice copying path. R has physical count 2 (its local plus V's backing); V has count 1. Transfer the producer owners into the frame, leaving no other mortal roots. Sparse indices are `[0,1]` in both cases.

| Same aggregate counts/storage | Frame values `[slot0,slot1]` | Reverse owner visits and resulting total |
| --- | --- | --- |
| V=2, F=1, Q=0, R=1; two Text headers; same data/frame/locals bytes | `[R,V]` | Visit V: destroys V, R remains count1. Visit R: destroys R inline. Finalize frame. **W=3**. |
| Identical counts, object kinds, lengths, refcounts and block multiset | `[V,R]` | Visit R: leaves its backing owner count1. Visit V: destroys V and queues R. Finalize frame and root, in either permitted order. **W=4**. |

`rc_bounded_frame_unit` decrements the sparse cursor before loading the corresponding owner (`219–223`). `rc_drop` distinguishes the last-view-root path (`92–105`). This is a hand-derived counterexample, **unexecuted**, to exact demand from aggregate lengths/kinds/owner counts/byte classes alone. Slot ordering differs; no claim is made that complete runtime states are identical. An exact algorithm allowed to inspect/simulate that order may distinguish them, but that is additional work/information excluded by the proposed aggregate certificate. A per-root count of incoming view edges still does not resolve this mixed-owner ordering case.

At the first public leave boundary, K1 may already have consumed one visit. The initial totals above include that work; the remaining certificate subtracts it. Snapshotting after the call without accounting for that first visit would change the comparison boundary.

## Obtaining a bound without a graph walk or new syntax

The necessary *local operands* already exist: record arity/kind, List kind/length, object cursor, frame written/remaining count, chunk occupancy, Text backing and allocation/deallocation identity. **The production aggregate certificate does not exist.** `pending_count` counts tasks; `rc_object_count/rc_bytes` are testing-only and include caches; `minyar_pool_used` includes frames/chunks/raw blocks but carries no slot demand. Summing lengths by traversing the heap at t would violate this task's target.

A hypothetical ledger maintained from program start can accumulate V, F, Q and R using those local operands, with no per-node/path table. Each successful reference-record construction adds arity plus one finalization if nonempty; scalar construction adds neither. A reference List append adds one visit after promotion; first promotion via append to an n-element immortal-only prefix adds n+1 visits and one finalization, whereas first promotion by replacement at length n adds n visits and one finalization. These are constant-many integer operations using `length`, despite the large value added. Future replacement after promotion adds no parent scan work; any new child allocation has its own generation charge. Promotion is permanent, including replacement of the last mortal value by an immortal (`minyar_collections.h:93–101,104–145,164–185`).

Heap-frame activation adds one finalization, even if it reuses a cached frame. The first non-null write to a previously unindexed local adds one visit; later replacement/move does not add another sparse visit. A new chunk adds one finalization and each accepted keep adds one visit. Detachment changes location only. Ordinary units subtract their tickets; a stack leave subtracts written visits without a frame-finalization ticket. Text allocation initially creates an owning-root token; an actual view construction reclassifies that header once, and mortal-to-cache promotion removes its root token. Root destruction subtracts it; enqueueing a last-view root moves R to Q without increasing Q+R. Full-range slices merely retain existing identity.

Those updates give the exact certificate when Text is absent and the sound interval with Text. They do not infer whether all root owners will actually close, nor certify source types/length bounds. The no-mortal-Text subset can be recognized conservatively by types; cohort closure and generation/length limits still need a separately justified function/workload contract. No whole-program inference algorithm is supplied. An offline event transcript can derive the same ledger, but the currently saved transcripts do not contain every required event for arbitrary programs.

**Prepromotion reservation.** To avoid a large instantaneous demand increase, uniformly reserve E=n+1 for every live immortal-only reference List, including empty and compiler-immutable Lists. Charge each append +1 even while its contents remain immortal. Promotion transfers E into actual visits/finalization rather than minting old-prefix credit; a first append needs only the ordinary new-slot +1. Indexed promotion needs no new parent credit. Final destruction without promotion discards the unused reserve. A purely static certificate may omit an immutable List's E only if no alias can later mutate it. The five-word runtime ledger cannot selectively omit it without remembering that choice: an extra per-allocation flag or a separately proved uniform allocation policy would be required, and its layout/admission consequences are outside this construction. Scalar Lists cannot become reference Lists under a valid typed ABI; unrestricted native reclassification is excluded.

The upper reserve is `Φ=V+F+Q+R+E`. In an open phase it may grow with allocations, new frame/chunk owners, appends and first writes. Scalar/immortal destruction can remove unused tokens. **Do not subtract an offered idle K from Φ:** `rc_service_pending` returns zero if no task is queued (`minyar_rc.h:95–100`), even when Φ represents large latent future work. Service units consumed before promotion cannot process the not-yet-retired prefix. This accounting does not bank empty-queue credit.

Φ is a certificate for *subsequent closure*, not cumulative open-phase work. A reference-slot replacement can destroy an old scalar leaf immediately while leaving the parent's future scan count unchanged; repeated replacements therefore need their own arrival/operation accounting. The scalar leaf's zero separate-finalizer weight cannot justify omitting that mutation's charged immediate work from an open-arrival model. Null/immortal fast paths likewise do not certify that a future insertion remains immortal.

Storage/cost of this hypothetical implementation is explicit: five checked 64-bit aggregate words (40 static bytes), constant-many additions/subtractions/tests per allocation, mutation, owner registration or ordinary cleanup unit, and the corresponding two decrements per fused pair. No per-object metadata or graph walk is required for these *global conservative* sums. Actual scheduler loops still execute their existing units. Checked overflow needs a declared failing/saturating policy; a saturated counter is only a conservative infinity/unknown, not an exact count. This cost is not zero or a WCET bound. If aggregates were pool-allocated together, 40 bytes would require a 64-byte block; static placement instead adds executable data outside pool charge. Any per-cohort attribution would need generation/cohort labels or a static no-cross-cohort-edge proof and is **not provided** by these five global words. No ledger has been added to production or executed here.

## Quantifying conservative charging from saved observations

The [saved accounting probe](evidence/runtime-demand-certificate/inputs/research/accounting-probes.json) used an immortal/null prefix of n entries and optionally one mortal owning Text. Its older main runtime hash is `db41660...`; the relevant collections/bounded-RC hashes match this checkpoint. Its assertion in the existing fixture is `total_work = promoted ? n+2 : 1`. These are saved observations, not reruns or proof premises.

| Prefix n | Saved unpromoted public release work | Unused List reserve n+1 | Saved promoted work, length n+1 |
| ---: | ---: | ---: | ---: |
| 7 | 1 | 8 | 9 |
| 63 | 1 | 64 | 65 |
| 1,023 | 1 | 1,024 | 1,025 |
| 16,383 | 1 | 16,384 | 16,385 |
| 65,534 | 1 | 65,535 | 65,536 |

At n=65,534, system/K1 records one task after promoted release, **557,153 requested bytes retained**, and 65,535 follow-up polls. Fixed/K32 records one task, 557,145 requested bytes retained and 2,047 follow-up polls. The reserve correctly anticipates length work, while the unpromoted public-release comparison exposes a 65,535-to-1 conservative ratio. The general Text upper bound adds one further token for the inserted owning Text; that token is unnecessary in this particular direct-last-slot shape, where its destruction is cocharged. A slot reservoir is sound but can be operationally useless when a large immortal-only List never promotes. The theorem's closure boundary normally releases roots through counted owner slots; these saved direct public releases have their own immediate-release allowance and must not be substituted unadjusted into V/F.

Shared DAG charging has a different pitfall. For a height-h binary DAG whose two fields at each level point to the *same* next allocation, there are h nonleaf two-field records plus one scalar leaf. Its own scan/finalization contribution is **3h**, not the exponential path expansion given by a recursively attached subtree weight `b(h)=3+2b(h−1)`. A global generation ledger counts two physical fields but charges the shared descendant's storage/work once. This hand family is unexecuted. Likewise, a List with m aliases to one scalar leaf costs m visits plus its one finalization, not m leaf-finalization tokens; leaf destruction is cocharged with the last visit.

## Four quantities that must remain separate

**1. Structural cleanup.** V/F/Q/R concern remaining reported units. They omit reference retains, dead-header cursor encoding, UTF8 work, initialization, copying, allocator metadata/free costs and closure bookkeeping. Record reference flags do not reduce scan length. Text can have a very large backing and only one finalization unit. A frame's `local_capacity` is a storage quantity; its sparse visit count is a work quantity.

**2. Logical versus retained storage.** Partition allocated managed blocks by logical reachability from semantic active roots, ignoring retired owner edges, then by dead-but-not-yet-freed identity. Views require inclusion of their actual root's entire byte capacity and any root/view Unicode index, once per allocation identity. A source-dead root retained by a *live* view is logically reachable through backing; its spare capacity is still private physical overhead. Add active/retired frame storage, chunks, cached empty frames, immortal cache blocks and any outside raw allocations as distinct terms. `rc_bytes` does not include all these terms.

For the frozen 64-bit fixed pool, let `q(x)` be the smallest power of two at least max(32,x). Header-inclusive charges are:

| Representation | Individual charged blocks |
| --- | --- |
| reference/scalar record with a fields | `q(16+9a)` / `q(16+8a)` |
| List, capacity c, allocated backing | `q(32)` plus `q(8+8c)`; omit NULL backing |
| owning Text | `q(48)` plus `q(8+d)` for actual allocated byte capacity d, plus `q(8+i)` if index payload i exists |
| Text view | `q(48)` plus its optional index block; root blocks are separately counted once |
| heap frame, capacity c | `q(64)` plus `q(16c)` if locals exist |
| temporary chunk | `q(80)=128`, even if partially occupied |
| actual stack frame | supplied 64-byte header plus 16 bytes per owner capacity; compiler stack layout/lifetime is a separate obligation |

Record/List layouts and allocation headers are in `minyar_runtime.c:53–84`, `minyar_collections.h:231–255`, `minyar_rc.h:27–50,109–157`; allocator rounding and retained resize overlap are in `minyar_pool.h:152–185,290–317`. A dead List's `capacity` is overwritten with its cursor; backing size must come from RcData or the allocation map, not that reused field. Cache charge uses `rc_heap_charge`, which is actual pool class for fixed/lazy but requested bytes for libc (`minyar_heap.h:26–39`).

Empty frame-cache charge is bounded by its configured 256 KiB cap, but is not cleanup debt. Integer cache entries retain immortal headers/backings (and possible later indexes); the 32,768-entry pointer table alone is 262,144 static bytes. ASCII Character storage is a separate static table. Pool storage P and map P/32 are reserved even when allocated-block charge is zero. These totals are not RSS; fixed pretouch does not lock pages, and lazy reservation is not guaranteed physical commitment.

The saved slice probe has one 513-byte survivor retaining an 8,192-capacity root: 8,418 total requested bytes in its generated case despite empty pending debt. This rejects a bound based on surviving token length or queued task count. The equal-credit experiment's 131,072-byte retained backing versus a compact result is another independently saved storage/admission separation.

**3. Contiguous admission.** Even a correct sum of all rounded blocks is not a proof that a next contiguous block exists. Raw fixed-pool allocation needs a nonempty adequate class (`minyar_pool.h:158–164`); growth also needs alignment/free exact buddies, or a replacement while old storage is still allocated (`267–317`). A simple canonical 4,096-byte example has 2,048 bytes free but every 32-byte cell alternating allocated/free; no 64-byte request can succeed. Adding labels/bytes to a work ledger does not recover free-block positions. The existing queue-empty scalar reservation theorem has its own final-block and matched-history premises; it is not transferred here. Equal-credit reuse and Bytes slack already failed later finite-pool admission despite favorable immediate counters.

**4. Service versus latency.** Once all roots are detached and only poll(k), 1<=k<=K, remains, a valid work-conserving scheduler needs exactly `ceil(W/k)` positive full-budget polls, counting a final partial poll. Already consumed exit/stack visits must first be deducted. Before root detachment, offered budget can be unused; after detachment, a known demand bound gives a service-opportunity bound, not seconds. No application supplies a maximum gap between opportunities here. An arbitrarily long scalar/foreign interval can offer none. Under new arrivals, bounded backlog requires a separate burst/arrival envelope and a lower service curve applied only when serviceable work exists. A finite total potential supplies neither such a curve nor an HFT deadline.

## Prior-art comparison and novelty disposition

CTRC's saved primary reading already establishes deferred outgoing decrements, lazy/eager simulation and acyclic empty-free-list count agreement (§2.4), uniform 32-byte cells with segmented objects (§2.3), and a variable-size EDA effect (§2.5). Minyar's unsplit Lists, sparse owner tables, cocharged leaves, flattened-root exception and buddy classes require a different concrete accounting relation. The current result is that relation for a closed subset; **constant-time lazy RC, segmentation, potential charging and allocation-driven service are not its novelty**.

The existing Niu–Hoffmann register records reading of introduction, cost semantics and sharing treatment under an immediate ideal collector. The Albert/Genaim/Gómez Zamalloa author manuscript was previously read only at abstract/introduction depth after an earlier publisher failure. Collector/lifetime-sensitive space reasoning and sharing-sensitive analysis therefore precede this task. This lane has not inspected their full proofs or established whether they already imply the proposed ledger under an instantiation. AARA and standard service-demand/potential reasoning likewise precede the scalar update equations. Network calculus was named in H2, but no primary network-calculus theorem was newly read or imported here.

Publication disposition: retain a conditional Minyar representation lemma, the two-owner exactness rejection and quantified promotion pessimism. Do not claim first-ever novelty, exhaustive predecessor exclusion, implemented inference or a verified theorem. Production disposition: **no change**. The global ledger has a concrete small hypothetical cost, but its workload usefulness, overflow policy and compiler preservation are unproved. An ambitious general no-syntax memory/admission certificate remains unsupported.

## Adversarial limitations and decisive next obligation

The theorem assumes all mortal roots close, correct compiler ownership, complete C transition correspondence and non-reentrant fusion. It cannot distinguish live unrelated allocations using five aggregate words, prove arbitrary source length/cohort bounds, or certify byte admission. Forgetting active chunks, sparse moved visits, a cached frame's reactivation, immortal cache bytes, a flattened backing root, current cursor, resizing overlap or a private carried child invalidates the respective quantity. Treating all scalar records as eliminated is wrong unless the actual compiler replacement proof applies. Acyclicity is not guaranteed for arbitrary native ABI callers.

The exact Text term needs last-owner ordering, not just refcounts. A promised exact general aggregate certificate is therefore rejected. The conservative prefix reserve remains sound but can be so pessimistic that it offers no useful scheduling threshold. No measured ledger overhead or compiler integration exists. The archived finite model/native cohorts do not discharge these proof obligations; their observer costs, representation exclusions and older hashes remain explicit.

The smallest decisive *future* experiment is the two Text owner orders above at K1, with the automatic leave poll included and all later poll work summed, plus exact root/view/frame/cache recovery. Expected totals are 3 and 4. A second analytic control can use the already saved n=65,534 prefix to compare actual work with reserve; rerunning the broad stopped model shapes is unnecessary and unauthorized. [Proposal](evidence/runtime-demand-certificate/decisive-proposal.json) is saved, **not run**.

For a stronger scientific result, the next required work is proof, not more attractive timing: discharge a C-to-ticket refinement including fusion, then a compiler-to-closed-cohort preservation lemma for a concrete function/workload. If either fails, retain the counterexample and narrow/reject the certificate. No follow-up execution, integration, optional tooling revival or campaign completion is authorized by this report.
