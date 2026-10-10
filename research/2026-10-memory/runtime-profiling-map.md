# Runtime workload coverage and next hypotheses

Static inventory, 4 October 2026. This records where evidence exists and where
additional profiling would answer a specific question. A test named below is an
available probe, not a claim that every version/profile ran in this campaign.
No candidate is justified solely by its source looking expensive. None of the
work-count observations establishes an operating-system latency bound.

| Runtime family | Existing focused checks | Campaign observations or gaps |
| --- | --- | --- |
| Scalar List growth and known-size `appended` construction | `runtime-unit.c`, `list-access.py`, performance runtime scaling | Guarded reservation has allocation-count, object/frame/chunk pressure controls and final paired C timings. Append improves; fixed ordinary growth retains about 1.6% higher CPU. Generated timing remains a separate gap. |
| Reference List ownership, replacement and promotion | `recursive-data.py`, `recursive-mutation.py`, memory profile regressions | First mortal insertion converts an immortal-only prefix into future scan work. Prepared immortal-prefix fixture separates pending tasks, work units and retained bytes. Sparse ownership metadata has not been added. |
| Text equality and short copying | `runtime-unit.c`, `runtime-cache.py`, compiler slice-cache probes | Existing overlapping fixed-width helpers cover short lengths. Need distinct distributions for equal strings, early/late mismatch, shared identity and lengths around 16; a changed helper must improve a generated workload rather than only a synthetic comparison loop. |
| Borrowed and consuming Text joins | binary-expression ownership, production ownership policy, recursive data | Indexed-Unicode consuming join was repaired. Known-ASCII borrowed copies now preserve certified counts after red/green counts, independent review and paired generated timing; byte-length-only control is about 0.9% slower. Deferred owners remain a separate research-only reuse policy experiment. |
| Text length, Unicode indexes and slicing | `runtime-unit.c`, `text-view-budget.py`, runtime indexing fixtures | Breadcrumb/cursor checks and actual destruction budgets exist. Need cold versus warm scans, forward/random/backward access, slice threshold boundaries and lifetime-weighted root retention. New joined-index checks cover accented/non-BMP values and 64/128 boundaries. |
| Bytes construction, refill and native extension | `runtime-bytes.c/.py`, conformance Bytes | Independent content model and counted zeroing exist. A test-only size-class-slack policy was rejected: later debt plus skipped growth service caused an allocation-admission regression. Other growth policies would require their own evidence. |
| Integer and Character Text formatting | integer cache and runtime cache probes | Cache warmth/range and cache-disabled inputs require separate cases. Existing integer caching consumes lasting capacity; replacing transient formatting with immortal data also changes cleanup service opportunities. |
| Float formatting and conversion | `runtime-numeric.c/.py`, numeric formatting fixtures | Independent binary64 roundtrip, exact spellings, notation cutoffs, asymmetric powers of two and libc-call counts already exist. Further algorithm work needs primary literature, independent shortest-decimal oracles and fractional/mixed negative controls. |
| Object/data allocation and cached frames | profile/configuration/memory contracts, generated stack sanitizer | Queue task counts do not bound bytes. Cached larger/smaller frames, sparse moved slots, temporary chunk boundaries and mixed record cursors are prepared kernel probes. Pool fragmentation/resize transactions need a separate allocation-state oracle. |
| File I/O and printing | runtime files, traps and conformance | Include latency only in an explicit end-to-end scenario. Printing flushes and file operations are external costs; exclude them from pure allocation/copy microbenchmarks and retain output checks outside the measured interval. |

There is no general public runtime hash-map or Text-to-number parsing API in
the inspected runtime fragments. Compiler token lookup and numeric parsing are
separate compiler workloads. The compiler-arena slice cache uses a small hash
plus exact byte equality; it does not establish application hash-table coverage.

## Ordered hypotheses and falsification criteria

1. **Deferred ownership blocks useful Text reuse.** Replay the same generated
   program at eager/K1/K8/K32, with a truly live alias, a retained view and self
   RHS controls. Count physical owners, extra service, copied prefix bytes,
   header/buffer reuse and retained requested/rounded storage. Reject an early
   poll policy if it exceeds the public-operation cleanup allowance, changes
   traps/evaluation order, mutates a live alias or worsens admission/retention.
   A nearby dead owner may clear while a deeper backlog does not; no generic
   success claim follows from a favorable isolated case.

2. **Known ASCII borrowed joins pay avoidable later scanning.** Both source
   counts can certify ASCII, while the pre-campaign `join_by_copying` created an
   unknown-count result. This preregistered hypothesis was executed and its
   narrowly scoped change accepted; final evidence is linked above. Count lazy-index calls/bytes visited on a
   generated borrowed join followed by `.length` or indexing; compare against
   unknown ASCII, Unicode, no-index-use and consuming-join controls. A proposed
   propagation rule must preserve the Unicode representation invariant just
   repaired. Reject if the scan saving is not material in a realistic workload,
   or extra hot-path decisions regress joins whose length is never queried.

3. **Finite-pool Bytes growth wastes capacity at size-class boundaries.**
   Measure requested capacity plus RcData/sentinel bytes and rounded blocks at
   visible lengths around powers of two, after clear/refill and self-append.
   Compare exact contents and service traces against the existing model. An
   alternative private growth policy must be checked under pending debt and
   fragmentation: changing growth frequency changes both copying and cleanup
   opportunities. Reject on slower representative serialization/refill, changed
   trap ordering or a worse finite-pool success boundary. No syntax addition is
   needed to investigate the current private policy.

4. **View copy thresholds trade copying for root retention.** Replay generated
   token batches with root sizes around 4096 and view sizes around one eighth
   of the root, vary the survival distribution and include flattened nested
   views. Track actually live root bytes separately from dead queued roots,
   requested backing capacity and rounded pool charge. A threshold that reduces
   one snapshot but adds enough copying/allocation to harm the full workload is
   rejected. Deliberately oversized C buffers are a stress control, not evidence
   that generated Text routinely has that spare capacity.

5. **Repeated Boolean formatting allocates unnecessarily.** Count ordinary
   `.text` formatting in a generated branch/log-record workload before proposing
   static immutable values. Existing Character/Integer caches are precedent,
   not a novelty claim. Test consuming Boolean-text joins, genuine aliases,
   no-format branches and finite-pool debt; removing allocations also removes
   their service hooks. Reject a cache-only microbenchmark result without a
   generated workload and explicit service/admission accounting.

6. **Immortal-prefix promotion creates large debt from one task.** Prepared
   fixture compares immortal-only retirement with one mortal tail insertion for
   prefixes through 65,534 elements. A useful result may simply quantify the
   limitation. A precise bitmap or sparse index would add header/storage costs,
   allocation failure paths and mutation invariants; do not introduce it before
   determining how often such prefixes occur and whether that complexity beats
   the current scheduler in representative mixed-reference collections.

The numbered hypotheses retain their original questions and rejection criteria.
Their completed or rejected findings are recorded in the runtime reports rather
than presented as still-unmeasured opportunities: List reservation and ASCII
metadata are accepted engineering changes; the specific Bytes slack policy is
rejected; isolated early service remains research-only. Accounting probes quantify
immortal-prefix debt and private scheduler boundary states without changing the
production ownership representation.

## Common experimental protocol

Use pinned before/after runtime and compiler artifacts, adjacent randomized
paired samples, exact output/content oracles and no observation deletion.
Keep setup, teardown and I/O outside a microbenchmark's interval but account for
them in a separate end-to-end workload. Retain allocation, copy, cleanup, pool
charge, peak/retained storage and timing as different measurements. Report
clock resolution, sample distributions and intervals rather than a best sample.
Recheck negative controls after any code-shape change. Host-starved timeouts
remain incomplete evidence, not correctness failures or throughput results.

For any admitted production change, require a red semantic/allocation regression
first, independent review of the invariant, the relevant existing gates and a
small maintainable portable CI regression. Research profile matrices can remain
explicit opt-ins. The campaign does not claim all APIs, inputs or papers have
been exhausted.


## Additional baseline observations during the frozen-source soak

[View/Boolean count probes](runtime-api-count-probes.md) now measure strict view
thresholds, exact versus geometric capacities, one versus 32 surviving tokens,
flattened nested slices and an actual ten-case generated token workload. They
show the expected single-token retention saving and a many-token copy cost at
an adjacent threshold boundary. They do not compare a changed policy on the same
input. Boolean conversions have allocation/service/index counts with a literal
control; generated Boolean workload and admission analysis remain unexecuted.
Text comparison mismatch distributions, cold/warm/random Unicode access costs,
allocator fragmentation state oracles still lack dedicated campaign performance
measurements. Integer-cache cold/warm range and lasting storage are now quantified
by the generated [Craft HUD projection](runtime-hud-formatting.md), without timings. These are gaps, not
permission to infer a speedup from source inspection.

A [queue-empty fragmentation differential](runtime-list-fragmentation.md) now
adds a bounded allocation-state/admission observation family, without proving
arbitrary buddy-state equivalence or allocator performance. Thirteen
[original peer-inspired regressions](runtime-peer-projections.md) add Bytes
slice independence, retained row alias/snapshot lifetime, unused literal
effects/order, once-only iterable evaluation, NaN comparison/negation and source
underflow/signed-zero bits, middle-literal effects and halfway binary64 arithmetic
plus wide-record mapping, embedded-NUL equality, loop capture, Euclidean
composition and extrema snapshots under actual O0/O2 links and generated ASan.
The earlier eight-method matrix and five later separate targeted matrices
remain distinct; a full thirteen-method run is not claimed. The older
projection sanitizer-O1 flag-order error is explicitly corrected in that report. They are already-correct coverage
additions, not new production fixes or literal upstream ports.

The [function-level ABI map](runtime-abi-evidence-map.md) now enumerates actual
source-defined public names and links only explicit evidence. Its unmapped fields
and source mentions do not assert that functions were never tested.


The [public Float-to-Text baseline](runtime-float-text.md) adds ten fixed
system/K32 native and sanitized C cases with exact managed allocation edges,
alias survival and recovery. It records offered idle service units separately
from zero actual queued work and the earlier private formatter/libc counts.
No Float-to-Text callsites were found in the inspected compiler/examples, so
this public ABI baseline is not an application hot-path or caching argument.

The [Unicode view source review](runtime-unicode-view-index-review.md) rejects
single-field known-count propagation: known character count with NULL offsets
selects the ASCII path in current Character and slice consumers. A Unicode count
alone could make length correct while access is wrong. Existing full slices and
ASCII slices already retain useful metadata; new root-coordinate/index ownership
or representation states are not justified by a measured workload and were not
introduced. The source-level lexer/escape pattern is documented without inferred
call frequency, execution or performance benefit. This hypothesis stops here.
