# Core patch inventory: accepted and joint final validation

The [exact own-production patch](evidence/runtime/core-production/own-production.patch)
contains only differences from the retained dirty runtime at campaign start,
not from HEAD. Its [hash/provenance index](evidence/runtime/core-production/index.json)
pins the three baseline and final files. A disposable application of that patch
to the dirty baseline reproduced every final file hash. Preexisting ownership,
allocator, Bytes, numeric and compiler changes are not attributed to this lane.
No commit/reset was performed. Native/application production work has its own
separate provenance.

| Change | Concrete problem and invariant | Red and final evidence | Acceptance and limitation |
| --- | --- | --- | --- |
| Guarded known-size List reservation, `minyar_collections.h` | Building an empty result through intermediate reallocations duplicates allocation/service work and retains intermediate arena storage. Plan the unchanged capacity schedule once only when pending task count is zero after header creation; any object/frame/chunk debt retains the full old growth loop. Ownership/copy loop is unchanged. Helpers remain private static inline via `MINYAR_HOT`. | [Allocation red](evidence/runtime/results/allocation-red.json); [final profile/generated matrix](evidence/runtime/results/list-sanitizer-matrix.json); [object debt](evidence/runtime/results/list-object-debt.json); [frame/chunk mutant controls](evidence/runtime/results/list-owner-debt.json); [paired timing](evidence/runtime/results/final-list-timing.json). | No-debt allocation reduction and paired append benefit justify it. A broader planner on ordinary growth and unconditional reservation were rejected. Fixed-pool ordinary growth retains about 1.6% higher CPU; generated growth timing is unmeasured. Timing pins its collection implementation and full recorded runtime snapshot, not a blanket latest-binary speed claim. |
| Indexed consuming Text join repair, `minyar_runtime.c` | Freeing offsets while retaining a known non-ASCII count incorrectly routes later Character/slice access through raw bytes. Preserve a known count only when both saved byte lengths equal their old character counts; otherwise invalidate to lazy indexing. Self RHS uses saved pre-mutation lengths. | [Native red](evidence/runtime/results/unicode-native-red.json); [generated red/green](evidence/runtime/results/unicode-generated-red-green.json); [exact final 107-check Text matrix](evidence/runtime/results/final-text-matrix.json), plus independent reviewers' distinct fixtures. | Required semantic correctness fix: length alone could pass while Characters/slices were wrong. Aliases/views, ASCII, Unicode stride boundaries and malformed UTF-8 traps retain behavior. No new cleanup policy or latency claim. |
| Certified ASCII borrowed-copy metadata, `minyar_runtime.c` | Copies of two known ASCII operands discarded their exact count and triggered a later redundant scan. Equal valid UTF-8 byte/scalar counts certify ASCII; copy result preserves their summed byte count, with NULL offsets. Unknown/Unicode operands stay unknown. | [Metadata red/counters](evidence/runtime/results/ascii-first-counts.json); [empty/view/cache/asymmetric controls](evidence/runtime/results/ascii-expanded-controls.json); [fixed sanitizer](evidence/runtime/results/ascii-fixed-sanitizer.json); [final lazy sanitizer](evidence/runtime/results/ascii-final-lazy-sanitizer.json); [paired generated timing](evidence/runtime/results/ascii-paired-timing.json); exact final Text matrix. | Local expression adds no fields, allocation or service hooks and saves known-ASCII scan work. Generated known workload ratio 2.392; no-query control about 0.9% slower, with all samples retained. Arena extension remains conservative; this optimizes the copy path. No general faster/real-time claim. |
| Bounded-RC description correction, `minyar_bounded_rc.h` | Top comment incorrectly described a tagged FIFO; source uses a recent stack and captured batch. | [Exact patch](evidence/runtime/core-production/own-production.patch), independent token-fingerprint verification and model provenance repin. | Comment only; no queue or budget behavior changed. |

Speculative extra service, equal-credit relocation, reverse destruction order,
Bytes slack capacity and new ownership metadata are not included. The rejected
same-credit prototype improves a measured reuse path but worsens finite-pool
admission; no default service policy was adopted.

Focused final matrices and completed ownership cohorts are scoped evidence.
The earlier full gate and coverage precede later changes; the unavailable final
integration lane is not described as a complete final-source all-clear.

The newer [joint own-production patch](evidence/runtime-joint-final/run-xc_5g2zj/own-production/own-production.patch) and [fresh reconstruction index](evidence/runtime-joint-final/run-xc_5g2zj/own-production/index.json) extend the historical inventory to exact final d919/3b hashes. They reproduce current files from the same retained initial dirty bytes; historical c4/01ae records remain unchanged.

| Joint change | Invariant and evidence | Current disposition |
| --- | --- | --- |
| Fresh scalar List prefix bulk copy | After the unchanged zero-debt reservation, copy the complete initialized nonoverlapping scalar prefix once; reference/debt paths retain the original loop. [Count/semantic evidence](runtime-list-bulk.md), [separate production CPU evidence](runtime-list-bulk-production-cpu.md) and [independent production review](runtime-scalar-production-performance-review.md) preserve raw-bit, pressure and adverse empty/reference controls. | Exact aca554 patch applied under root release. [Focused combined-source checks](runtime-joint-final-results.json) passed; final endurance and terminal review remain pending. No application-hot-path claim. |
| Aggregate certified ASCII count | Carry an existing ASCII certificate through the existing fragment sizing pass, with unchanged allocation and all-poll order. Unknown/Unicode operands stay conservative. [Count/event controls](runtime-aggregate-join.md) and [independent timing audit](performance-evidence-audit.md) qualify the4096-byte/five-fragment2.4808 ratio and small adverse controls. | Exact87b8 patch applied under root release; same focused final gates passed. The two earlier long cohorts excluded this path; dedicated final-source endurance remains pending. |
