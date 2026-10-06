# Rejected Bytes capacity-slack experiment

Selected raw results, source diffs and hashes survive `make clean` in the
[durable runtime index](evidence/runtime/index.json); original acquisition paths
remain recorded there.

4 October 2026. The inspected pool Bytes policy uses capacities 16, 32, 64, …
while the allocation includes an eight-byte RcData header and one-byte sentinel.
At a visible length of 5,000, capacity 8,192 requests 8,201 backing bytes and
charges a 16,384-byte buddy block. A private capacity of 8,183 fits an 8,192-byte
block. That arithmetic motivates a measurement; it is not a correctness defect,
a measured application improvement or a proof of a universally better policy.

The test-only candidate rounds the ordinary proposed capacity plus header and
sentinel into a pool block, then exposes that block's unused tail as private
capacity. It applies only if no retirement task is pending at the growth call;
system/arena behavior is unchanged. No public Bytes capacity API or ownership
syntax is added. The candidate is retained only in an external runtime snapshot.

## Decisive late-debt negative control

`tests/memory-research-bytes-debt-pressure.c` creates empty-start Bytes and adds
16 bytes while no debt exists. Both variants have the identical 32-byte backing
block; original capacity is 16 and candidate capacity is 23. A separate live
64-field mixed record charges 1,024 pool bytes. The fixture fills a 64 KiB pool,
leaves one 32-byte upper buddy for potential buffer growth, retires the record
and performs explicit field visits until exactly one finalization unit remains.
Debt was deliberately created **after** the idle capacity choice.

The seventeenth append has different effects:

- Original grows capacity 16→32, services the last retirement unit, frees the
  1,024-byte record and grows its backing into the reserved upper buddy.
- Candidate fits within capacity 23, performs no growth/service, saves 32
  backing bytes but leaves the 1,024-byte retired record occupying the pool.

Both preserve every appended byte. The next operation is the public
`fileExists` API on an already-existing immutable 1,023-byte path. Its path
conversion requires one raw 1,024-byte heap block. Original succeeds, returns
false for the nonexistent overlong path and reclaims the entire pool. Candidate
fails with bounded-heap exhaustion. Smaller total occupancy does not make a
fragmented 32-byte hole substitute for the unavailable 1,024-byte block.

Final differential evidence:
[run-tm7tl7ch/results.json](evidence/runtime/results/rejected-bytes-policy.json).
Eight isolated builds/runs cover original/candidate × fixed/lazy × O2/ASan+UBSan
at K1. All four originals succeed with complete recovery, and all four candidates
fail with the expected OOM. Exact fixture/runtime hashes, candidate text,
commands, outputs and diagnostics are retained. LeakSanitizer is disabled. No
timing comparison was performed, no production Bytes source changed, and no
virtual-capacity bookkeeping was introduced.

## Interpretation and allocator boundary

The pending-at-growth guard cannot recover the original history after the
candidate selected a larger idle capacity. Clear/shrink/bulk append and
nonzero initial lengths make that history more complicated than a function of
current visible length. Restoring it would need extra capacity history or new
service policy. The present allocation-saving hypothesis does not justify that
complexity under the user's simplicity requirement.

This rejects this candidate and guard, not every possible smaller-buffer policy.
Its favorable idle rounding arithmetic remains valid, but cannot establish
equivalent admission under the observed late-debt trace. Alternative policies
would require their own red/green contents, service and pressure controls.

`text_as_path` intentionally calls raw `rc_heap_allocate` rather than managed
object/data allocation. Raw transient path storage is outside `rc_bytes` and
has no automatic RC service hook. The current contract budgets managed
allocation, not every raw heap or file operation; this trace does not establish
an independent allocator defect. Adding service there would be a separate
policy change requiring its own baseline/TDD and accounting of the entire file
operation. It must not be smuggled in to rescue a failed capacity experiment.

Further baseline work can measure charged/requested bytes, resize calls, copied
bytes and cleanup units on generated serialization/refill at intermediate and
exact class-boundary sizes, with mutable aliases, self-append, native extension
and clear/resize controls. That would characterize the tradeoff, not overturn
this admission counterexample automatically.
